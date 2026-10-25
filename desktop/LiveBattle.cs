using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Management;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

// A status file is telemetry, never execution authorization. Launch uses a separate fresh CLI check.
class LiveBattleReport {
    public string SessionId,RunDirectory,StatusPath,State,Reason,Player,Commander,CommanderId,ConnectionId,Side,Summary,Plan,Feedback;
    public int HostPid;
    public bool Verified,Fresh,HostAlive,CanStop;
    public List<string> Checks=new List<string>();
}
class LiveBattleReader {
    readonly string root;readonly Action<Dictionary<string,object>> verifyGame;readonly Func<int,DateTime,bool> hostIsAlive;readonly bool verifyHostLifetime;
    const string ExeDigest="ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165";
    public LiveBattleReader(string bridgeRoot):this(bridgeRoot,VerifyGame,(pid,written)=>HostIsAlive(pid,written,Path.GetFullPath(bridgeRoot))){verifyHostLifetime=true;}
    internal LiveBattleReader(string bridgeRoot,Action<Dictionary<string,object>> gameCheck,Func<int,DateTime,bool> hostCheck){root=Path.GetFullPath(bridgeRoot);verifyGame=gameCheck;hostIsAlive=hostCheck;}
    public static Dictionary<string,object> Object(object value){var result=value as Dictionary<string,object>;if(result==null)throw new InvalidDataException("对象格式无效");return result;}
    public static object Get(Dictionary<string,object> value,string key){object result;return value.TryGetValue(key,out result)?result:null;}
    public static string Str(Dictionary<string,object> value,string key){return Convert.ToString(Get(value,key),CultureInfo.InvariantCulture);}
    static int Num(Dictionary<string,object> value,string key){return Convert.ToInt32(Get(value,key),CultureInfo.InvariantCulture);}
    static bool Yes(Dictionary<string,object> value,string key){return Get(value,key) is bool && (bool)Get(value,key);}
    Dictionary<string,object> Read(string path){if(new FileInfo(path).Length>1048576)throw new InvalidDataException("状态文件超过上限");return Object(new JavaScriptSerializer{MaxJsonLength=1048576}.DeserializeObject(File.ReadAllText(path,Encoding.UTF8)));}
    public static bool Within(string path,string parent){string full=Path.GetFullPath(path),folder=Path.GetFullPath(parent).TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar;return full.StartsWith(folder,StringComparison.OrdinalIgnoreCase);}
    public static string Hash(string path){using(var sha=SHA256.Create())using(var stream=File.OpenRead(path))return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-","").ToLowerInvariant();}
    static void Need(bool ok,string reason){if(!ok)throw new InvalidDataException(reason);}
    static void VerifyGame(Dictionary<string,object> session){using(var game=Process.GetProcessById(Num(session,"pid"))){
        var expected=DateTimeOffset.Parse(Str(session,"start_time"),CultureInfo.InvariantCulture);Need(Math.Abs((game.StartTime.ToUniversalTime()-expected.UtcDateTime).TotalMilliseconds)<1,"游戏PID已重用或创建时间不符");
        Need(string.Equals(Path.GetFullPath(game.MainModule.FileName),Path.GetFullPath(Str(session,"game")),StringComparison.OrdinalIgnoreCase),"游戏映像路径不符");Need(Hash(game.MainModule.FileName)==ExeDigest,"游戏可执行版本不受支持");
    }}
    [DllImport("shell32.dll",SetLastError=true)]static extern IntPtr CommandLineToArgvW([MarshalAs(UnmanagedType.LPWStr)]string command,out int count);
    [DllImport("kernel32.dll")]static extern IntPtr LocalFree(IntPtr pointer);
    static bool HostIsAlive(int pid,DateTime written,string bridgeRoot){try{using(var host=Process.GetProcessById(pid)){
        if(host.HasExited || host.StartTime.ToUniversalTime()>written || !host.ProcessName.StartsWith("python",StringComparison.OrdinalIgnoreCase))return false;
        using(var query=new ManagementObjectSearcher("SELECT CommandLine FROM Win32_Process WHERE ProcessId="+pid))using(var rows=query.Get())foreach(ManagementObject row in rows){
            int count;IntPtr pointer=CommandLineToArgvW(Convert.ToString(row["CommandLine"]),out count);if(pointer==IntPtr.Zero)return false;
            try{var args=new List<string>();for(int n=0;n<count;n++)args.Add(Marshal.PtrToStringUni(Marshal.ReadIntPtr(pointer,n*IntPtr.Size)));
                string script=Path.Combine(bridgeRoot,"integration","battle_host.py"),session=Path.Combine(bridgeRoot,"acceptance","active-session.json");
                bool scriptMatches=args.Any(a=>Path.IsPathRooted(a) && string.Equals(Path.GetFullPath(a),script,StringComparison.OrdinalIgnoreCase));
                for(int n=0;n<args.Count-1;n++)if(args[n]=="--session" && Path.IsPathRooted(args[n+1]) && string.Equals(Path.GetFullPath(args[n+1]),session,StringComparison.OrdinalIgnoreCase))return scriptMatches;
            }finally{LocalFree(pointer);}
        }
    }}catch{}return false;}
    static IEnumerable<Dictionary<string,object>> Rows(object value){var rows=value as IEnumerable;if(rows==null || value is string)yield break;foreach(var item in rows){var row=item as Dictionary<string,object>;if(row!=null)yield return row;}}
    static string Safe(object value){return RuntimeStatus.Safe(Convert.ToString(value,CultureInfo.InvariantCulture));}
    static string Counters(Dictionary<string,object> status,string key,params string[] names){object raw=Get(status,key);if(raw==null)return "暂无";var item=Object(raw);return string.Join("  ",names.Select(n=>n+" "+Safe(Get(item,n))));}
    static string MissionName(string value){switch(value){case "attack":return "主攻";case "raid":return "骚扰";case "combined_arms":return "协同";default:return Safe(value);}}
    static string MissionPhase(string value){switch(value){case "reserved":return "待接管";case "approach":return "接近";case "prepare":return "交战准备";case "engage":return "交战";case "retreat":return "撤退";case "restored":return "控制已归还";default:return Safe(value);}}
    static string MissionText(Dictionary<string,object> status){
        if(Get(status,"missions")==null)return "";
        var board=Object(Get(status,"missions"));var text=new StringBuilder("\r\n连续任务（跨策略刷新保留）");
        var active=Rows(Get(board,"active")).Take(4).ToList();
        foreach(var mission in active.Concat(Rows(Get(board,"recent_history")).Reverse().Take(3))){
            var observations=Get(mission,"observations") as Dictionary<string,object>;
            string phase=MissionPhase(Str(mission,"phase"));
            if(observations!=null && Yes(observations,"disposed_verified"))phase="单位已消失，控制已释放";
            else if(observations!=null && Yes(observations,"no_dispatch_verified"))phase="未接管，已取消";
            string result=Str(mission,"terminal_status");
            text.Append("\r\n").Append(MissionName(Str(mission,"module"))).Append(" · ").Append(phase);
            if(!string.IsNullOrEmpty(result))text.Append(" · ").Append(result=="completed"?"效果已核验":result=="failed"?"目标未完成":result=="cancelled"?"已取消":Safe(result));
            text.Append(" / 已证实伤害 ").Append(observations==null?"0":Safe(Get(observations,"source_damage_amount")));
            text.Append(" / 伤害遥测 ").Append(Safe(Get(mission,"reported_damage")));
            if(!string.IsNullOrEmpty(Str(mission,"retreat_requested_reason")))text.Append(" / 已请求撤退");
        }
        if(active.Count==0)text.Append("\r\n当前没有接管中的任务");
        if(Get(board,"effect_coverage")!=null)foreach(var item in Object(Get(board,"effect_coverage")))text.Append("\r\n已核验效果 ").Append(MissionName(item.Key)).Append(" ").Append(Safe(Get(Object(item.Value),"completed")));
        return text.ToString();
    }
    static string PlanText(Dictionary<string,object> status){
        if(Get(status,"current_plan")==null){
            string state=Str(status,"state");
            if(state=="result_candidate")return "已检测到结算信号，宿主已停止派单。胜负请以游戏结算核对。";
            if(state=="stopped")return "宿主已停止，当前没有活跃计划。";
            if(state=="fault")return "宿主因故障停止派单，当前没有活跃计划。请查看执行反馈。";
            return state=="paused"?"游戏已暂停，暂停期间不请求模型。":"宿主尚无当前计划。";
        }
        var p=Object(Get(status,"current_plan"));var output=new StringBuilder();
        foreach(string name in new[]{"plan_id","origin","stance","production_focus","economy_policy","tech_policy","objective_region","expires_at_game_seconds"})if(Get(p,name)!=null)output.AppendLine(name+": "+Safe(Get(p,name)));
        if(Get(p,"budget")!=null)foreach(var entry in Object(Get(p,"budget")))output.AppendLine("预算 "+Safe(entry.Key)+": "+Safe(entry.Value));
        foreach(var task in Rows(Get(p,"tactical_tasks")))output.AppendLine("战术 "+Safe(Get(task,"module"))+" / "+Safe(Get(task,"purpose"))+" → "+Safe(Get(task,"target_region")));
        return output.ToString();
    }
    internal void VerifyPreflight(Dictionary<string,object> check,CommanderProfile commander){
        string sessionPath=Path.Combine(root,"acceptance","active-session.json");byte[] initial=File.ReadAllBytes(sessionPath);var session=Read(sessionPath);
        string run=Path.GetFullPath(Str(session,"run_directory"));Need(Within(run,Path.Combine(root,"acceptance","runs")),"活动run目录不属于验收会话");
        Need(Yes(check,"can_start") && Yes(check,"computer_verified") && Yes(check,"package_verified") && Yes(check,"production_evidence_verified") && Str(check,"reason_code")=="ready","宿主未授权启动");
        Need(Str(check,"session_id")==Str(session,"session_id") && Str(check,"commander_id")==commander.id && Num(check,"player_id")==3,"检查结果与所选UUID/会话/玩家不符");
        verifyGame(session);
        string package=Str(session,"mod_big");Need(Path.IsPathRooted(package) && Hash(package)==Str(session,"mod_sha256"),"MOD包已改变");
        string config=Str(session,"mod_config");var entries=File.ReadAllLines(config).Select(x=>x.Trim()).Where(x=>x.StartsWith("add-big ",StringComparison.OrdinalIgnoreCase)).ToArray();
        Need(entries.Length==1 && string.Equals(Path.GetFullPath(Path.Combine(Path.GetDirectoryName(config),entries[0].Substring(8).Trim().Trim('"'))),Path.GetFullPath(package),StringComparison.OrdinalIgnoreCase),"MOD配置引用不符");
        var registry=Read(Str(session,"registry"));Need(Str(registry,"registry_revision")==Str(session,"registry_revision") && Str(registry,"package_sha256")==Str(session,"mod_sha256") && Yes(registry,"compiled_ids_verified"),"注册表/编译包不符");
        var registered=Rows(Get(registry,"commanders")).SingleOrDefault(x=>Str(x,"id")==commander.id);Need(registered!=null && Str(registered,"connection_id")==commander.connection_id,"所选档案连接未匹配游戏注册");
        string identityPath=Path.Combine(run,"battle-host","identity.json");var identity=Read(identityPath);var native=Object(Get(identity,"native"));var actual=Object(Get(identity,"binding"));
        Need(Str(identity,"session_id")==Str(session,"session_id") && Num(identity,"pid")==Num(session,"pid") && Str(identity,"mod_sha256")==Str(session,"mod_sha256"),"采集身份不属于当前活动会话");
        var identityAge=DateTime.UtcNow-File.GetLastWriteTimeUtc(identityPath);Need(identityAge>=TimeSpan.FromSeconds(-2) && identityAge<TimeSpan.FromSeconds(20),"身份采集已过期或时间无效");
        Need(Str(actual,"commander_id")==commander.id && Str(actual,"connection_id")==commander.connection_id && Str(actual,"registry_revision")==Str(session,"registry_revision") && Yes(actual,"compiled_ids_verified") && Yes(actual,"session_package_matches") && Yes(actual,"personality_binding_verified"),"真实UUID人格绑定未通过");
        Need(Num(native,"player_index")==3 && Yes(native,"store_membership_verified") && Yes(native,"side_matches_player") && !string.IsNullOrEmpty(Str(native,"ai_player")) && Str(native,"ai_player")!="0x0","真实电脑身份不符");
        Need(Rows(Get(registered,"assets")).Any(x=>Str(x,"asset_id")==Str(actual,"asset_id") && Str(x,"instance_id")==Str(native,"instance_id") && Str(x,"side")==Str(actual,"side")),"原生人格asset/instance不符");
        Need(!File.Exists(Path.Combine(run,"battle-host","stop.json")),"当前会话已有停止标记，需要新会话");
        Need(!Read().HostAlive,"当前会话宿主已运行，禁止重复启动");
        Need(File.ReadAllBytes(sessionPath).SequenceEqual(initial),"活动会话在核验中改变");
    }
    public LiveBattleReport Read(){
        var report=new LiveBattleReport();
        try{
            string sessionPath=Path.Combine(root,"acceptance","active-session.json");byte[] initial=File.ReadAllBytes(sessionPath);var session=Read(sessionPath);
            Guid id;report.SessionId=Str(session,"session_id");Need(Guid.TryParse(report.SessionId,out id),"会话 UUID 无效");
            report.RunDirectory=Path.GetFullPath(Str(session,"run_directory"));Need(Within(report.RunDirectory,Path.Combine(root,"acceptance","runs")),"run目录不属于验收会话");
            report.StatusPath=Path.Combine(report.RunDirectory,"battle-host","host-status.json");var status=Read(report.StatusPath);
            Need(Num(status,"schema_version")==1 && Str(status,"kind")=="battle_host_v1" && Str(status,"source")=="game_bridge","非真实宿主协议");
            Need(Str(status,"session_id")==report.SessionId && Num(status,"pid")==Num(session,"pid") && Str(status,"process_start")==Str(session,"start_time") && Str(status,"mod_sha256")==Str(session,"mod_sha256") && Str(status,"registry_revision")==Str(session,"registry_revision"),"宿主会话绑定不匹配");
            report.Checks.Add("会话 / run目录 / 宿主元数据一致");
            report.State=Str(status,"state");Need(new[]{"initializing","waiting_game","sampling_wait","running","paused","stopped","fault","result_candidate"}.Contains(report.State),"未知宿主阶段");report.Reason=Str(status,"reason_code");
            report.HostPid=Num(status,"host_pid");var age=DateTime.UtcNow-File.GetLastWriteTimeUtc(report.StatusPath);report.Fresh=age.TotalSeconds>=-2 && age.TotalSeconds<=20;report.HostAlive=hostIsAlive(report.HostPid,File.GetLastWriteTimeUtc(report.StatusPath));
            if(report.HostAlive && verifyHostLifetime){try{using(var process=Process.GetProcessById(report.HostPid))report.HostAlive=Get(status,"host_creation_filetime")!=null && process.StartTime.ToUniversalTime().ToFileTimeUtc()==Convert.ToInt64(Get(status,"host_creation_filetime")) && Math.Abs((process.StartTime.ToUniversalTime()-DateTimeOffset.Parse(Str(status,"host_start_time")).UtcDateTime).TotalMilliseconds)<1;}catch{report.HostAlive=false;}}
            report.Checks.Add("状态新鲜度: "+(report.Fresh?"20秒内":"历史/过期")+"；host PID/命令行: "+(report.HostAlive?"通过":"未运行或未核验"));
            var binding=Object(Get(status,"binding"));report.Player=Str(binding,"player_id");report.Commander=Str(binding,"commander_name");report.CommanderId=Str(binding,"commander_id");report.ConnectionId=Str(binding,"connection_id");
            Guid commanderId,connectionId;Need(Guid.TryParse(report.CommanderId,out commanderId) && Guid.TryParse(report.ConnectionId,out connectionId),"指挥官或连接UUID无效");
            report.Plan=PlanText(status);
            var execution=Object(Get(status,"execution"));
            report.Summary="玩家 "+Safe(report.Player)+" / "+Safe(report.Commander)+" / "+(Yes(binding,"computer_verified")?"宿主报告电脑身份已核验":"宿主尚未核验电脑身份")+"\r\n会话 "+report.SessionId+"\r\n阶段 "+Safe(report.State)+" / "+Safe(report.Reason)+"\r\n执行器 "+(Yes(execution,"executor_connected")?"已连接":"未连接")+" / "+(Yes(execution,"dry_run")?"dry-run":"真实执行模式")+" / 当前派单 "+(Yes(execution,"enabled")?"开启":"关闭");
            report.Feedback="模型: "+Counters(status,"metrics","requests","accepted","rejected","timeouts","plan_changes")+"\r\n传输: "+Counters(status,"transport","attempts","retries","responses")+"\r\n记忆: "+Counters(status,"memory","context_builds","compactions","max_payload_bytes")+"\r\n任务: "+Counters(status,"task_counters","dispatches","started","completed","failed","blocked");
            if(Get(status,"visibility")!=null){var view=Object(Get(status,"visibility"));report.Feedback+="\r\n视野 玩家 "+Safe(Get(view,"viewer_player_id"))+" / 已核验 "+Safe(Get(view,"verified"))+" / 当前可见 "+Safe(Get(view,"currently_visible"))+" / 历史联系 "+Safe(Get(view,"last_seen"));}
            if(Get(status,"tactical")!=null){var tactical=Object(Get(status,"tactical"));if(Get(tactical,"counters")!=null)foreach(var module in Object(Get(tactical,"counters"))){var count=Object(module.Value);report.Feedback+="\r\n"+Safe(module.Key)+" 接受 "+Safe(Get(count,"accepted"))+" / 开始 "+Safe(Get(count,"started"))+" / 完成 "+Safe(Get(count,"completed"))+" / 失败 "+Safe(Get(count,"failed"));}}
            if(Get(status,"last_result")!=null){var result=Object(Get(status,"last_result"));report.Feedback+="\r\n最新反馈: "+Safe(Get(result,"status"))+" / "+Safe(Get(result,"reason_code"));}
            if(Get(status,"latest_snapshot")!=null){var snap=Object(Get(status,"latest_snapshot"));report.Feedback+="\r\n快照 #"+Safe(Get(snap,"snapshot_id"))+" / 游戏秒 "+Safe(Get(snap,"game_time_seconds"))+" / 暂停 "+Safe(Get(snap,"paused"));if(Get(snap,"resources")!=null)report.Feedback+=" / 资金 "+Safe(Get(Object(Get(snap,"resources")),"credits"));}
            foreach(var job in Rows(Get(status,"jobs")).Take(16))report.Feedback+="\r\n任务 "+Safe(Get(job,"module"))+" / "+Safe(Get(job,"purpose"))+" / "+Safe(Get(job,"status"))+" / "+Safe(Get(job,"reason_code"));
            string missionText=MissionText(status);report.Feedback=missionText+(missionText.Length>0?"\r\n":"")+report.Feedback;
            verifyGame(session);
            report.Checks.Add("游戏PID / 创建时间 / 映像 / SHA256通过");
            string package=Str(session,"mod_big");Need(Path.IsPathRooted(package) && Hash(package)==Str(session,"mod_sha256"),"MOD包已改变");
            string config=Str(session,"mod_config");var entries=File.ReadAllLines(config).Select(x=>x.Trim()).Where(x=>x.StartsWith("add-big ",StringComparison.OrdinalIgnoreCase)).ToArray();
            Need(entries.Length==1 && string.Equals(Path.GetFullPath(Path.Combine(Path.GetDirectoryName(config),entries[0].Substring(8).Trim().Trim('"'))),Path.GetFullPath(package),StringComparison.OrdinalIgnoreCase),"MOD配置包引用不符");
            report.Checks.Add("MOD包hash / 配置引用通过");
            var registry=Read(Str(session,"registry"));Need(Str(registry,"registry_revision")==Str(session,"registry_revision") && Str(registry,"package_sha256")==Str(session,"mod_sha256") && Yes(registry,"compiled_ids_verified"),"注册表修订或编译包不符");
            var registered=Rows(Get(registry,"commanders")).SingleOrDefault(x=>Str(x,"id")==Str(binding,"commander_id"));Need(registered!=null && Str(registered,"connection_id")==Str(binding,"connection_id"),"注册表UUID/连接不符");
            var identity=Read(Path.Combine(report.RunDirectory,"battle-host","identity.json"));var native=Object(Get(identity,"native"));var actual=Object(Get(identity,"binding"));report.Side=Str(actual,"side");
            Need(Yes(binding,"computer_verified") && Str(actual,"commander_id")==Str(binding,"commander_id") && Str(actual,"connection_id")==Str(binding,"connection_id") && Str(actual,"registry_revision")==Str(session,"registry_revision") && Yes(actual,"compiled_ids_verified") && Yes(actual,"session_package_matches") && Yes(actual,"personality_binding_verified"),"采集的UUID人格绑定未通过");
            Need(Num(native,"player_index")==Num(binding,"player_id") && Yes(native,"store_membership_verified") && Yes(native,"side_matches_player") && !string.IsNullOrEmpty(Str(native,"ai_player")) && Str(native,"ai_player")!="0x0","采集的电脑玩家原生身份不符");
            Need(Rows(Get(registered,"assets")).Any(x=>Str(x,"asset_id")==Str(actual,"asset_id") && Str(x,"instance_id")==Str(native,"instance_id") && Str(x,"side")==report.Side),"原生人格asset/instance不符");
            report.Checks.Add("registry / 玩家索引 / UUID / 原生人格asset一致");
            Need(File.ReadAllBytes(sessionPath).SequenceEqual(initial),"核验过程中活动会话改变");
            report.Verified=true;
            report.CanStop=report.Verified && report.Fresh && report.HostAlive && new[]{"initializing","sampling_wait","running","paused"}.Contains(report.State);
        }catch(Exception e){report.Verified=false;report.CanStop=false;report.Checks.Add("未通过: "+(e is InvalidDataException?RuntimeStatus.Safe(e.Message):e is FileNotFoundException || e is DirectoryNotFoundException?"会话或宿主文件尚未生成":e is ArgumentException?"对应进程已结束或字段无效":"文件/进程校验不可用"));}
        return report;
    }
    public void RequestStop(LiveBattleReport displayed){
        var fresh=Read();Need(displayed!=null && fresh.CanStop && fresh.SessionId==displayed.SessionId && fresh.StatusPath==displayed.StatusPath && fresh.HostPid==displayed.HostPid && fresh.Player==displayed.Player && fresh.CommanderId==displayed.CommanderId && fresh.ConnectionId==displayed.ConnectionId,"宿主身份或运行状态改变，停止请求未写入");
        string path=Path.Combine(fresh.RunDirectory,"battle-host","stop.json"),temp=path+"."+Guid.NewGuid().ToString("N")+".tmp";
        File.WriteAllText(temp,new JavaScriptSerializer().Serialize(new{session_id=fresh.SessionId}),new UTF8Encoding(false));
        if(File.Exists(path))File.Replace(temp,path,null);else File.Move(temp,path);
    }
}

class LiveBattlePage : UserControl {
    readonly LiveBattleReader reader;readonly HostLauncher launcher;readonly Label summary=new Label(),checks=new Label(),launchState=new Label();readonly TextBox plan=Box(),feedback=Box();readonly DarkButton stop=new DarkButton(),begin=new DarkButton(),preflight=new DarkButton();readonly DarkComboBox chooser=new DarkComboBox();
    readonly Func<IEnumerable<CommanderProfile>> profiles;readonly Func<bool> unsaved;
    readonly System.Windows.Forms.Timer timer=new System.Windows.Forms.Timer{Interval=3000};LiveBattleReport displayed;HostReadiness readiness;bool busy,launchBusy;bool observing;volatile bool closed;
    static TextBox Box(){return new TextBox{Multiline=true,ReadOnly=true,ScrollBars=ScrollBars.Vertical,BackColor=Color.FromArgb(17,21,19),ForeColor=Color.FromArgb(226,218,191),BorderStyle=BorderStyle.FixedSingle,Dock=DockStyle.Fill};}
    public LiveBattlePage(string bridgeRoot,string libraryFile,Func<IEnumerable<CommanderProfile>> commanderProfiles,Func<bool> hasUnsaved){
        profiles=commanderProfiles;unsaved=hasUnsaved;reader=new LiveBattleReader(bridgeRoot);launcher=new HostLauncher(bridgeRoot,libraryFile);BackColor=Color.FromArgb(28,30,29);ForeColor=Color.FromArgb(226,218,191);
        var grid=new TableLayoutPanel{Dock=DockStyle.Fill,Padding=new Padding(18),ColumnCount=1,RowCount=9};
        foreach(float h in new[]{38f,46f,55f,100f,110f,24f,80f,24f,-1f})grid.RowStyles.Add(h<0?new RowStyle(SizeType.Percent,100):new RowStyle(SizeType.Absolute,h));
        chooser.Dock=DockStyle.Fill;chooser.SelectedIndexChanged+=(s,e)=>{readiness=null;begin.Enabled=false;launchState.Text="已更换所选档案；请检查当前真实玩家UUID绑定。";};grid.Controls.Add(chooser,0,0);VisibleChanged+=(s,e)=>{if(Visible)RefreshProfiles();};
        var actions=new FlowLayoutPanel{Dock=DockStyle.Fill};var watch=new DarkButton{Text="观察当前会话",Width=120,Height=36};preflight.Text="检查启动条件";preflight.Width=120;preflight.Height=36;begin.Text="开始指挥";begin.Primary=true;begin.Enabled=false;begin.Width=100;begin.Height=36;stop.Text="停止宿主派单";stop.Enabled=false;stop.Width=120;stop.Height=36;var detach=new DarkButton{Text="停止观察",Width=100,Height=36};
        watch.Click+=async(s,e)=>{observing=true;timer.Start();await RefreshHost();};detach.Click+=(s,e)=>{observing=false;timer.Stop();stop.Enabled=false;checks.Text="本窗口观察已停止；宿主与游戏继续运行。";};
        preflight.Click+=async(s,e)=>await CheckLaunch();begin.Click+=async(s,e)=>await StartLaunch();
        stop.Click+=async(s,e)=>{stop.Enabled=false;try{await Task.Run(()=>reader.RequestStop(displayed));checks.Text="已请求停止派单与模型调用，等待宿主反馈。游戏与原生AI继续。";}catch{checks.Text="停止未发送：会话/宿主校验已变化，请刷新。";}};
        actions.Controls.AddRange(new Control[]{watch,preflight,begin,stop,detach});grid.Controls.Add(actions,0,1);launchState.Dock=summary.Dock=checks.Dock=DockStyle.Fill;launchState.ForeColor=Color.FromArgb(205,169,94);launchState.Text="开始会调用真实模型，仅启用已实测的生产与战术能力。先在游戏选择同名指挥官并进入战局，再检查条件。";summary.Text="仅观察当前 active-session 的真实宿主；尚未读取。";checks.ForeColor=Color.FromArgb(176,166,135);checks.Text="停止派单仅写匹配会话的 stop.json；不关闭游戏。任意JSON不能启用接管。";grid.Controls.Add(launchState,0,2);grid.Controls.Add(summary,0,3);grid.Controls.Add(checks,0,4);
        grid.Controls.Add(new Label{Text="当前策略 / 宿主负责执行",Dock=DockStyle.Fill},0,5);grid.Controls.Add(plan,0,6);grid.Controls.Add(new Label{Text="任务反馈 / 记忆 / 模型与传输计数",Dock=DockStyle.Fill},0,7);grid.Controls.Add(feedback,0,8);Controls.Add(grid);
        timer.Tick+=async(s,e)=>await RefreshHost();Disposed+=(s,e)=>{closed=true;timer.Dispose();};
        RefreshProfiles();
    }
    void RefreshProfiles(){string selected=chooser.SelectedItem is CommanderProfile?((CommanderProfile)chooser.SelectedItem).id:null;chooser.Items.Clear();foreach(var p in profiles())chooser.Items.Add(p);for(int n=0;n<chooser.Items.Count;n++)if(((CommanderProfile)chooser.Items[n]).id==selected){chooser.SelectedIndex=n;return;}if(chooser.Items.Count>0)chooser.SelectedIndex=0;}
    CommanderProfile Selected(){var p=chooser.SelectedItem as CommanderProfile;return p==null?null:new CommanderProfile{id=p.id,name=p.name,connection_id=p.connection_id,model=p.model,personality=p.personality,traits=p.traits};}
    async Task CheckLaunch(){if(launchBusy)return;launchBusy=true;begin.Enabled=false;preflight.Enabled=false;var selected=Selected();bool changed=unsaved();launchState.Text="正在运行只读游戏检查；会生成本地采样文件，不请求模型或注入。";try{var result=await Task.Run(()=>launcher.Check(selected,changed));if(IsDisposed)return;readiness=result;launchState.Text=result.Reason;observing=true;timer.Start();await RefreshHost();}finally{launchBusy=false;if(!IsDisposed){preflight.Enabled=true;UpdateLaunch();}}}
    async Task StartLaunch(){if(launchBusy)return;launchBusy=true;begin.Enabled=false;preflight.Enabled=false;chooser.Enabled=false;var selected=Selected();bool changed=unsaved();var expected=readiness;launchState.Text="开始前重新检查活动会话、所选UUID与生产证据…";try{int pid=await Task.Run(()=>launcher.Start(expected,selected,changed,()=>closed || unsaved()));if(IsDisposed)return;readiness=null;launchState.Text="真实宿主已启动（PID "+pid+"），等待本局兵营、30秒自然生产观察和执行器握手；模型与生产派单由宿主控制。";observing=true;timer.Start();await RefreshHost();}catch(Exception error){if(!IsDisposed){readiness=null;launchState.Text=error is InvalidDataException?RuntimeStatus.Safe(error.Message):"宿主未启动：进程/文件检查失败，请重新检查。";}}finally{launchBusy=false;if(!IsDisposed){preflight.Enabled=true;chooser.Enabled=true;UpdateLaunch();}}}
    void UpdateLaunch(){var selected=Selected();begin.Enabled=!launchBusy && readiness!=null && readiness.CanStart && DateTime.UtcNow-readiness.CheckedUtc<TimeSpan.FromSeconds(20) && selected!=null && selected.id==readiness.CommanderId && selected.connection_id==readiness.ConnectionId && !unsaved() && !(displayed!=null && displayed.HostAlive);}
    async Task RefreshHost(){UpdateLaunch();if(busy || IsDisposed)return;busy=true;try{var value=await Task.Run(()=>reader.Read());if(IsDisposed || !observing)return;displayed=value;summary.Text=(value.Summary??"尚无可展示的真实宿主状态。")+(string.IsNullOrEmpty(value.Side)?"":"\r\n阵营/角色: "+RuntimeStatus.Safe(value.Side)+" / 电脑指挥官");checks.Text=string.Join("\r\n",value.Checks);plan.Text=value.Plan??"—";feedback.Text=(value.Verified?"会话与文件核验通过。":"未验证遥测 / 禁止控制。")+"\r\n"+(value.Feedback??"—");stop.Enabled=value.CanStop;UpdateLaunch();}finally{busy=false;}}
}
