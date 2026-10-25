using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Web.Script.Serialization;

class HostReadiness {
    public bool CanStart;public string Reason,SessionId,CommanderId,ConnectionId;public DateTime CheckedUtc;
    public Dictionary<string,string> Fingerprints=new Dictionary<string,string>();
}
class HostCommandResult {public int ExitCode;public string Output;}
class HostLauncher {
    readonly string root,libraryPath,python;readonly LiveBattleReader reader;
    readonly Func<ProcessStartInfo,HostCommandResult> checkProcess;readonly Func<ProcessStartInfo,int> startProcess;
    public HostLauncher(string bridgeRoot,string libraryFile):this(bridgeRoot,libraryFile,new LiveBattleReader(bridgeRoot),RunCheck,StartHost){}
    internal HostLauncher(string bridgeRoot,string libraryFile,LiveBattleReader validator,Func<ProcessStartInfo,HostCommandResult> check,Func<ProcessStartInfo,int> start){
        root=Path.GetFullPath(bridgeRoot);libraryPath=Path.GetFullPath(libraryFile);reader=validator;checkProcess=check;startProcess=start;
        python=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),".cache","codex-runtimes","codex-primary-runtime","dependencies","python","python.exe");
    }
    static HostCommandResult RunCheck(ProcessStartInfo info){
        info.RedirectStandardOutput=true;info.RedirectStandardError=true;
        using(var process=Process.Start(info)){
            var output=process.StandardOutput.ReadToEndAsync();var errors=process.StandardError.ReadToEndAsync();
            if(!process.WaitForExit(45000)){try{process.Kill();}catch{}throw new InvalidDataException("只读宿主检查超时，请检查游戏战局");}
            Task.WaitAll(output,errors);return new HostCommandResult{ExitCode=process.ExitCode,Output=output.Result};
        }
    }
    static int StartHost(ProcessStartInfo info){using(var process=Process.Start(info))return process.Id;}
    public static string Quote(string value){
        if(value==null)throw new ArgumentNullException("value");var result=new StringBuilder("\"");int slashes=0;
        foreach(char c in value){if(c=='\\'){slashes++;continue;}if(c=='"'){result.Append('\\',slashes*2+1);result.Append('"');slashes=0;continue;}result.Append('\\',slashes);slashes=0;result.Append(c);}result.Append('\\',slashes*2);return result.Append('"').ToString();
    }
    internal ProcessStartInfo Command(string commanderId,bool check){
        Guid uuid;if(!Guid.TryParse(commanderId,out uuid))throw new InvalidDataException("指挥官 UUID 无效");
        string evidenceRun=Path.Combine(root,"acceptance","runs","20261024-183816-commander");
        var args=new List<string>{Path.Combine(root,"integration","battle_host.py"),"--session",Path.Combine(root,"acceptance","active-session.json"),"--commander",uuid.ToString("D"),"--player","3","--library",libraryPath,"--execute","--with-visibility","--evidence",Path.Combine(evidenceRun,"production-trace-20261024-184048-9696c7b3.json"),"--persistent-evidence",Path.Combine(evidenceRun,"persistent-production-status.json")};
        string tactical=Path.Combine(root,"integration","tactical-capabilities.json");
        if(File.Exists(tactical)){args.Add("--tactical-evidence");args.Add(tactical);}
        return new ProcessStartInfo(python,string.Join(" ",args.Select(Quote))+(check?" --check":"")){UseShellExecute=false,CreateNoWindow=true,WorkingDirectory=root,WindowStyle=ProcessWindowStyle.Hidden};
    }
    IEnumerable<string> Inputs(){
        string evidence=Path.Combine(root,"acceptance","runs","20261024-183816-commander");
        var inputs=new List<string>{Path.Combine(root,"acceptance","active-session.json"),libraryPath,Path.Combine(root,"integration","battle_host.py"),Path.Combine(evidence,"production-trace-20261024-184048-9696c7b3.json"),Path.Combine(evidence,"persistent-production-status.json"),Path.Combine(evidence,"persistent-production.jsonl")};
        foreach(string name in new[]{"integration","strategy","visibility","tactical"}){
            string directory=Path.Combine(root,name);if(!Directory.Exists(directory))continue;
            inputs.AddRange(Directory.GetFiles(directory,"*.py",SearchOption.AllDirectories));
            if(name=="tactical"){
                inputs.AddRange(Directory.GetFiles(directory,"*.dll",SearchOption.AllDirectories));
                inputs.AddRange(Directory.GetFiles(directory,"*.exe",SearchOption.AllDirectories));
            }
        }
        foreach(string name in new[]{"build-capability-2d7873e1.json","template-safety-2d7873e1.json"}){string path=Path.Combine(root,"visibility",name);if(File.Exists(path))inputs.Add(path);}
        string manifest=Path.Combine(root,"integration","tactical-capabilities.json");if(File.Exists(manifest))inputs.Add(manifest);
        return inputs.Distinct(StringComparer.OrdinalIgnoreCase);
    }
    static bool Yes(Dictionary<string,object> obj,string name){return LiveBattleReader.Get(obj,name) is bool && (bool)obj[name];}
    public HostReadiness Check(CommanderProfile selected,bool unsaved){
        var readiness=new HostReadiness{CheckedUtc=DateTime.UtcNow,CommanderId=selected==null?null:selected.id,ConnectionId=selected==null?null:selected.connection_id};
        try{
            if(selected==null || unsaved)throw new InvalidDataException("请先保存所选指挥官和连接配置，再检查启动条件");
            foreach(string path in Inputs())readiness.Fingerprints[path]=LiveBattleReader.Hash(path);
            var persisted=new CommanderLibrary(Path.GetDirectoryName(libraryPath));var profile=persisted.Data.commanders.SingleOrDefault(x=>x.id==selected.id);
            if(profile==null || profile.connection_id!=selected.connection_id || profile.name!=selected.name || profile.model!=selected.model || profile.traits!=selected.traits || profile.personality!=selected.personality)throw new InvalidDataException("所选档案与已保存配置不一致");
            var connection=persisted.FindConnection(profile.connection_id);if(connection==null || connection.credential_load_failed || string.IsNullOrWhiteSpace(connection.key) || string.IsNullOrWhiteSpace(persisted.EffectiveModel(profile)))throw new InvalidDataException("此档案的持久化密钥或模型尚未就绪");
            string secret=Path.Combine(Path.GetDirectoryName(libraryPath),"secrets",connection.id+".dpapi");readiness.Fingerprints[secret]=LiveBattleReader.Hash(secret);
            string evidenceRun=Path.Combine(root,"acceptance","runs","20261024-183816-commander");var evidence=LiveBattleReader.Object(new JavaScriptSerializer().DeserializeObject(File.ReadAllText(Path.Combine(evidenceRun,"production-trace-20261024-184048-9696c7b3.json"))));string stream=LiveBattleReader.Str(evidence,"stream");if(!LiveBattleReader.Within(stream,evidenceRun))throw new InvalidDataException("生产证据流不属于固定验收run");readiness.Fingerprints[stream]=LiveBattleReader.Hash(stream);
            var result=checkProcess(Command(selected.id,true));string line=(result.Output??"").Split(new[]{'\r','\n'},StringSplitOptions.RemoveEmptyEntries).LastOrDefault();
            if(line==null || line.Length>65536)throw new InvalidDataException("宿主检查没有返回有效结果");
            var check=LiveBattleReader.Object(new JavaScriptSerializer().DeserializeObject(line));string reason=LiveBattleReader.Str(check,"reason_code");readiness.SessionId=LiveBattleReader.Str(check,"session_id");
            if(result.ExitCode!=0 || !Yes(check,"can_start"))throw new InvalidDataException(reason=="fresh_process_required"?"fresh_process_required：本进程已使用长驻执行器，请重新开局并记录新会话":"宿主检查未通过："+RuntimeStatus.Safe(reason));
            reader.VerifyPreflight(check,profile);EnsureUnchanged(readiness);
            readiness.CanStart=true;readiness.CheckedUtc=DateTime.UtcNow;readiness.Reason="已通过正式--check与独立会话/UUID核验；开始时复查视野与能力证据，仅启用已实测的指挥能力。";
        }catch(Exception error){readiness.CanStart=false;readiness.Reason=error is InvalidDataException?RuntimeStatus.Safe(error.Message):"启动条件检查失败：文件、配置或进程不可用。";}
        return readiness;
    }
    internal static void EnsureUnchanged(HostReadiness readiness){foreach(var item in readiness.Fingerprints)if(LiveBattleReader.Hash(item.Key)!=item.Value)throw new InvalidDataException("配置/活动会话/证据在检查中改变，请重新检查");}
    public int Start(HostReadiness displayed,CommanderProfile selected,bool unsaved,Func<bool> invalidated=null){
        if(displayed==null || !displayed.CanStart || selected==null || displayed.CommanderId!=selected.id || displayed.ConnectionId!=selected.connection_id)throw new InvalidDataException("请选择档案并重新检查启动条件");
        var fresh=Check(selected,unsaved);if(!fresh.CanStart)throw new InvalidDataException(fresh.Reason);
        if(fresh.SessionId!=displayed.SessionId)throw new InvalidDataException("活动会话已改变，请重新检查后再开始");
        foreach(var item in displayed.Fingerprints){string current;if(!fresh.Fingerprints.TryGetValue(item.Key,out current) || current!=item.Value)throw new InvalidDataException("上次检查后配置或证据改变，请重新检查");}
        EnsureUnchanged(fresh);if(invalidated!=null && invalidated())throw new InvalidDataException("界面已关闭或配置被修改，本次启动取消");return startProcess(Command(selected.id,false));
    }
}
