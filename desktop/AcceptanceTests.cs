using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

class AcceptanceTests {
    static string run;static int checks;
    static void Require(bool ok,string name){if(!ok)throw new Exception(name);checks++;Console.WriteLine("PASS "+name);}
    static object Field(object value,string name){return value.GetType().GetField(name,BindingFlags.NonPublic|BindingFlags.Instance).GetValue(value);}
    static object Call(object value,string name,params object[] args){return value.GetType().GetMethod(name,BindingFlags.NonPublic|BindingFlags.Instance).Invoke(value,args);}
    static void Reject(Action action,string name){bool failed=false;try{action();}catch{failed=true;}Require(failed,name);}
    static void StoreTests(){
        string root=Path.Combine(run,"library");var lib=new CommanderLibrary(root);
        Require(lib.Data.commanders.Count==3 && lib.Data.commanders.Select(p=>p.connection_id).Distinct().Count()==1,"three profiles reuse one connection");
        var a=lib.Data.connections[0];var b=lib.Data.connections[1];string aId=a.id;string pId=lib.Data.commanders[0].id;
        a.default_model="model-A";a.key="FAKE-SECRET-A";a.remember_key=true;b.key="FAKE-SECRET-B";b.remember_key=true;
        Require(lib.EffectiveModel(lib.Data.commanders[0])=="model-A","profile inherits connection default model");
        lib.Data.commanders[1].model="model-override";Require(lib.EffectiveModel(lib.Data.commanders[1])=="model-override","profile model override is independent");
        a.name="改名后的共享连接";lib.Data.commanders[0].name="改名后的铁锤";lib.Save();
        string document=File.ReadAllText(Path.Combine(root,"library.v2.json"));string exported=File.ReadAllText(Path.Combine(root,"commander-bindings.json"));
        Require(!document.Contains("FAKE-SECRET") && !exported.Contains("FAKE-SECRET") && !exported.Contains("base_url"),"library and binding export omit secrets/endpoints");
        var reload=new CommanderLibrary(root);Require(reload.Data.connections[0].id==aId && reload.Data.commanders[0].id==pId,"renaming preserves stable UUIDs");
        Require(reload.Data.connections[0].key=="FAKE-SECRET-A" && reload.Data.connections[1].key=="FAKE-SECRET-B","DPAPI secrets round-trip independently per connection");
        Require(Directory.GetFiles(Path.Combine(root,"secrets"),"*.dpapi").Length==2,"two independent encrypted key files");
        string brokenSecret=Path.Combine(root,"secrets",b.id+".dpapi");byte[] invalid=new byte[]{1,2,3,4};File.WriteAllBytes(brokenSecret,invalid);
        var partial=new CommanderLibrary(root);Require(partial.Data.connections[1].credential_load_failed && partial.Data.connections[1].key=="" && partial.Data.connections[0].key=="FAKE-SECRET-A" && partial.Data.commanders.Count==3,"single DPAPI failure preserves library and other credentials");
        partial.Save();Require(File.ReadAllBytes(brokenSecret).SequenceEqual(invalid),"saving unrelated changes preserves unreadable credential bytes");
        partial.Data.connections[1].key="FAKE-SECRET-B";partial.Save();reload=new CommanderLibrary(root);Require(!reload.Data.connections[1].credential_load_failed && reload.Data.connections[1].key=="FAKE-SECRET-B","explicit key re-entry repairs only selected connection");
        reload.Data.connections[0].remember_key=false;reload.Save();var forgotten=new CommanderLibrary(root);
        Require(forgotten.Data.connections[0].key=="" && forgotten.Data.connections[1].key=="FAKE-SECRET-B","forgetting one key preserves the other connection");
        string before=File.ReadAllText(Path.Combine(root,"library.v2.json"));forgotten.Data.commanders[0].connection_id=Guid.NewGuid().ToString("D");
        Reject(()=>forgotten.Save(),"invalid connection reference is rejected");Require(before==File.ReadAllText(Path.Combine(root,"library.v2.json")),"failed validation preserves saved library");
        string legacyRoot=Path.Combine(run,"legacy");Directory.CreateDirectory(legacyRoot);
        string oldJson="{\"provider\":\"DeepSeek\",\"base_url\":\"https://api.deepseek.com\",\"model\":\"legacy-model\",\"personality\":2,\"traits\":\"legacy-traits\"}";
        byte[] oldSecret=ProtectedData.Protect(Encoding.UTF8.GetBytes("FAKE-LEGACY-KEY"),null,DataProtectionScope.CurrentUser);
        File.WriteAllText(Path.Combine(legacyRoot,"config.json"),oldJson);File.WriteAllBytes(Path.Combine(legacyRoot,"key.dpapi"),oldSecret);
        var legacy=new CommanderLibrary(legacyRoot);Require(legacy.MigratedLegacy && !File.Exists(Path.Combine(legacyRoot,"library.v2.json")),"legacy migration is read-only until explicit save");
        Require(legacy.Data.connections[0].key=="FAKE-LEGACY-KEY" && legacy.EffectiveModel(legacy.Data.commanders[0])=="legacy-model","legacy model and encrypted key migrate into memory");
        legacy.Save();Require(File.ReadAllText(Path.Combine(legacyRoot,"config.json"))==oldJson && File.ReadAllBytes(Path.Combine(legacyRoot,"key.dpapi")).SequenceEqual(oldSecret),"saving v2 preserves original legacy files");
        string corruptRoot=Path.Combine(run,"corrupt");Directory.CreateDirectory(corruptRoot);string corruptPath=Path.Combine(corruptRoot,"library.v2.json");File.WriteAllText(corruptPath,"{broken-library");Reject(()=>new CommanderLibrary(corruptRoot),"corrupt library is not silently reset");
        using(var recovery=new CommanderHub(corruptRoot)){Require((bool)Field(recovery,"loadFailed"),"corrupt library opens explicit read-only recovery");Call(recovery,"Save");Require(File.ReadAllText(corruptPath)=="{broken-library","recovery save cannot overwrite original library");}
        Uri uri;Require(!CommanderLibrary.TryEndpoint("http://example.com",out uri) && !CommanderLibrary.TryEndpoint("https://user:secret@example.com",out uri) && !CommanderLibrary.TryEndpoint("https://example.com/v1/chat/completions",out uri),"remote HTTP, URL credentials and full request paths rejected");
        string fixtures=Path.GetFullPath(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"..","strategy","fixtures"));
        foreach(string name in new[]{"offline-status.json","idle-status.json","fallback-status.json"}){RuntimeStatus.Parse(File.ReadAllText(Path.Combine(fixtures,name)));Require(true,"strategy fixture accepted: "+name);}
        var demo=RuntimeStatus.Demo(lib.Data.commanders[0],1);var json=new JavaScriptSerializer();string raw=json.Serialize(demo);
        Require(RuntimeStatus.Parse(raw).binding.computer_verified==false,"offline target is never a verified real computer");
        Reject(()=>RuntimeStatus.Parse(raw.Replace("\"simulation\"","\"game\"")),"unverified real-game status rejected");
        Reject(()=>RuntimeStatus.Parse(raw.Replace("\"enabled\":false","\"enabled\":true")),"status claiming active execution rejected");
        Require(RuntimeStatus.Safe("Authorization: Bearer abc").Contains("隐藏"),"sensitive status text is redacted");
    }
    static void LiveTests(){
        string root=Path.Combine(run,"live-fixture"),dir=Path.Combine(root,"acceptance","runs","sample"),host=Path.Combine(dir,"battle-host");Directory.CreateDirectory(host);
        string sessionPath=Path.Combine(root,"acceptance","active-session.json"),statusPath=Path.Combine(host,"host-status.json"),registryPath=Path.Combine(root,"registry.json"),modPath=Path.Combine(root,"fixture.big"),configPath=Path.Combine(root,"fixture.skudef");
        var serializer=new JavaScriptSerializer();Action<string,object> write=(path,value)=>File.WriteAllText(path,serializer.Serialize(value));
        string sid=Guid.NewGuid().ToString("D"),cid=Guid.NewGuid().ToString("D"),connection=Guid.NewGuid().ToString("D"),start=DateTimeOffset.Now.ToString("o");
        File.WriteAllText(modPath,"FAKE-MOD-FOR-FILESYSTEM-VALIDATION");File.WriteAllText(configPath,"add-big fixture.big");string digest=LiveBattleReader.Hash(modPath);
        var session=new Dictionary<string,object>{{"session_id",sid},{"run_directory",dir},{"pid",123},{"start_time",start},{"mod_sha256",digest},{"mod_big",modPath},{"mod_config",configPath},{"registry",registryPath},{"registry_revision","fixture-revision"}};
        var binding=new Dictionary<string,object>{{"player_id",3},{"commander_id",cid},{"commander_name","测试指挥官"},{"connection_id",connection},{"computer_verified",true}};
        var status=new Dictionary<string,object>{{"schema_version",1},{"kind","battle_host_v1"},{"source","game_bridge"},{"session_id",sid},{"pid",123},{"process_start",start},{"host_pid",456},{"mod_sha256",digest},{"registry_revision","fixture-revision"},{"binding",binding},{"state","running"},{"reason_code","fixture_only"},{"execution",new{enabled=true,dry_run=false,executor_connected=true}},{"memory",new{compactions=3,max_payload_bytes=8192}},{"task_counters",new{dispatches=2,started=1,completed=1,failed=0,blocked=0}}};
        status["missions"]=new{active=new[]{new{module="attack",phase="approach",reported_damage=5,observations=new{source_damage_amount=0}}},recent_history=new object[0],effect_coverage=new{attack=new{completed=0}}};
        write(sessionPath,session);write(statusPath,status);
        write(registryPath,new{registry_revision="fixture-revision",package_sha256=digest,compiled_ids_verified=true,commanders=new[]{new{id=cid,connection_id=connection,assets=new[]{new{asset_id="fixture-asset",instance_id="0x123",side="Soviet"}}}}});
        write(Path.Combine(host,"identity.json"),new{native=new{player_index=3,store_membership_verified=true,side_matches_player=true,ai_player="0x456",instance_id="0x123"},binding=new{commander_id=cid,connection_id=connection,registry_revision="fixture-revision",compiled_ids_verified=true,session_package_matches=true,personality_binding_verified=true,asset_id="fixture-asset",side="Soviet"}});
        // Process probes are replaced only inside this isolated filesystem test. UI always uses real probes.
        var reader=new LiveBattleReader(root,s=>{},(pid,written)=>true);var report=reader.Read();
        Require(report.Verified && report.Fresh && report.HostAlive && report.CanStop,"live fixture validates session/package/registry/native UUID chain");
        Require(report.Player=="3" && report.Side=="Soviet" && report.Feedback.Contains("compactions 3"),"live telemetry renders bound role and memory counters");
        Require(report.Feedback.Contains("主攻 · 接近 / 已证实伤害 0 / 伤害遥测 5") && report.Feedback.Contains("已核验效果 主攻 0"),"unqualified damage telemetry never appears as a verified tactical effect");
        reader.RequestStop(report);string stopPath=Path.Combine(host,"stop.json");Require(File.ReadAllText(stopPath)==serializer.Serialize(new{session_id=sid}),"stop request contains only exact active-session UUID");File.Delete(stopPath);
        File.SetLastWriteTimeUtc(statusPath,DateTime.UtcNow.AddMinutes(-2));Require(!reader.Read().CanStop && !reader.Read().Fresh,"stale telemetry cannot enable stop");Reject(()=>reader.RequestStop(report),"stop revalidates freshness before any write");Require(!File.Exists(stopPath),"rejected stop leaves no request file");write(statusPath,status);
        Require(!new LiveBattleReader(root,s=>{},(pid,written)=>false).Read().CanStop,"missing host process cannot enable stop");
        Require(!new LiveBattleReader(root,s=>{throw new InvalidDataException("fixture PID reused");},(pid,written)=>true).Read().Verified,"game process validation failure blocks control");
        status["session_id"]=Guid.NewGuid().ToString("D");write(statusPath,status);Require(!reader.Read().Verified,"foreign session telemetry rejected");status["session_id"]=sid;
        binding["commander_id"]=Guid.NewGuid().ToString("D");write(statusPath,status);Require(!reader.Read().Verified,"foreign commander UUID rejected by registry");binding["commander_id"]=cid;write(statusPath,status);
        File.AppendAllText(modPath,"changed");Require(!reader.Read().Verified,"changed package hash blocks control");File.WriteAllText(modPath,"FAKE-MOD-FOR-FILESYSTEM-VALIDATION");
        session["run_directory"]=Path.Combine(root,"outside-runs");write(sessionPath,session);Require(!reader.Read().Verified,"run directory traversal rejected");session["run_directory"]=dir;write(sessionPath,session);
        status["source"]="simulation";write(statusPath,status);Require(!reader.Read().Verified,"simulated source cannot become real host telemetry");
        Require(!LiveBattleReader.Within(Path.Combine(root,"acceptance","runs-other","x"),Path.Combine(root,"acceptance","runs")),"sibling prefix does not satisfy run containment");
        string libDir=Path.Combine(root,"library");var lib=new CommanderLibrary(libDir);var profile=lib.Data.commanders[0];profile.id=cid;profile.connection_id=connection;var conn=lib.Data.connections[0];string oldId=conn.id;conn.id=connection;foreach(var p in lib.Data.commanders)if(p.connection_id==oldId)p.connection_id=connection;conn.key="FAKE-LAUNCH-KEY";conn.remember_key=true;conn.default_model="fake-model";lib.Save();
        write(Path.Combine(host,"identity.json"),new{session_id=sid,pid=123,mod_sha256=digest,native=new{player_index=3,store_membership_verified=true,side_matches_player=true,ai_player="0x456",instance_id="0x123"},binding=new{commander_id=cid,connection_id=connection,registry_revision="fixture-revision",compiled_ids_verified=true,session_package_matches=true,personality_binding_verified=true,asset_id="fixture-asset",side="Soviet"}});
        string evidenceDir=Path.Combine(root,"acceptance","runs","20261024-183816-commander"),integration=Path.Combine(root,"integration");Directory.CreateDirectory(evidenceDir);Directory.CreateDirectory(integration);string stream=Path.Combine(evidenceDir,"trace.jsonl");File.WriteAllText(stream,"FAKE-TRACE");write(Path.Combine(evidenceDir,"production-trace-20261024-184048-9696c7b3.json"),new{stream=stream});File.WriteAllText(Path.Combine(evidenceDir,"persistent-production-status.json"),"FAKE-PERSISTENT");File.WriteAllText(Path.Combine(evidenceDir,"persistent-production.jsonl"),"FAKE-AUDIT");File.WriteAllText(Path.Combine(integration,"battle_host.py"),"FAKE-HOST-NEVER-EXECUTED");
        var checkedValue=new Dictionary<string,object>{{"can_start",true},{"computer_verified",true},{"package_verified",true},{"production_evidence_verified",true},{"reason_code","ready"},{"session_id",sid},{"commander_id",cid},{"player_id",3}};int checksRun=0,startsRun=0;
        var launcher=new HostLauncher(root,Path.Combine(libDir,"library.v2.json"),new LiveBattleReader(root,s=>{},(pid,written)=>false),info=>{checksRun++;Require(info.UseShellExecute==false && info.Arguments.EndsWith(" --check"),"preflight invokes shell-free check mode only");return new HostCommandResult{ExitCode=0,Output=serializer.Serialize(checkedValue)};},info=>{startsRun++;Require(!info.Arguments.EndsWith(" --check") && info.UseShellExecute==false && info.CreateNoWindow,"start launches one hidden shell-free formal host");return 987;});
        var ready=launcher.Check(profile,false);Require(ready.CanStart,"formal check plus independent fixture chain permits start");int checkedBefore=checksRun;Require(launcher.Start(ready,profile,false)==987 && checksRun==checkedBefore+1 && startsRun==1,"start repeats formal check then launches exactly one host");
        Require(!launcher.Check(profile,true).CanStart,"unsaved configuration blocks formal start");checkedValue["commander_id"]=Guid.NewGuid().ToString("D");Require(!launcher.Check(profile,false).CanStart,"formal check for foreign commander cannot unlock start");checkedValue["commander_id"]=cid;
        checkedValue["can_start"]=false;checkedValue["reason_code"]="fresh_process_required";var consumed=launcher.Check(profile,false);Require(!consumed.CanStart && consumed.Reason.Contains("fresh_process_required"),"consumed process has explicit fresh-process requirement");Reject(()=>launcher.Start(ready,profile,false),"fresh recheck refusal prevents host launch");Require(startsRun==1,"failed fresh recheck never starts host");
        Require(HostLauncher.Quote("C:\\folder with space\\")=="\"C:\\folder with space\\\\\"" && HostLauncher.Quote("a\"b")=="\"a\\\"b\"","Windows argument quoting preserves spaces/trailing slashes/quotes");
    }
    static async Task FormTests(CommanderHub form){
        var provider=(ComboBox)Field(form,"providers");var key=(TextBox)Field(form,"key");var endpoint=(TextBox)Field(form,"endpoint");var model=(TextBox)Field(form,"testModel");var state=(Label)Field(form,"modelState");
        key.Text="FAKE-SWITCH-KEY";provider.SelectedIndex=1;Require(key.Text=="","provider switch clears only selected connection key");Require(endpoint.Text=="https://api.deepseek.com" && model.Text=="deepseek-flash","DeepSeek endpoint and default model presets");
        var begin=(Button)Field(form,"begin");Require(!begin.Enabled,"real start disabled before capability acceptance");Call(form,"StartDemo");
        var targets=(ComboBox)Field(form,"targets");Require(targets.Items.Count==1 && targets.Items[0].ToString().Contains("离线样例") && !targets.Enabled,"offline target is explicitly marked and not a real selector");
        Require(!begin.Enabled,"offline plan cannot unlock real start");Call(form,"StopLocal");Require(!((System.Windows.Forms.Timer)Field(form,"watch")).Enabled,"stop cancels only local observer timer");
        string fixture=Path.GetFullPath(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"..","strategy","fixtures","offline-status.json"));Call(form,"ReadStatus",fixture);Require(!begin.Enabled,"imported simulated strategy cannot unlock real start");
        provider.SelectedIndex=2;var picker=new TcpListener(IPAddress.Loopback,0);picker.Start();int port=((IPEndPoint)picker.LocalEndpoint).Port;picker.Stop();
        using(var server=new HttpListener()){
            server.Prefixes.Add("http://127.0.0.1:"+port+"/");server.Start();endpoint.Text="http://127.0.0.1:"+port;model.Text="mock-model";key.Text="FAKE-HTTP-KEY";
            string[] replies={"{\"choices\":[{\"message\":{\"content\":\"OK\"}}]}","{\"choices\":[]}"};
            for(int n=0;n<2;n++){
                string reply=replies[n];
                var serve=Task.Run(()=>{var context=server.GetContext();using(var reader=new StreamReader(context.Request.InputStream)){string body=reader.ReadToEnd();Require(body.Contains("mock-model") && body.Contains("max_tokens"),"custom request contains selected default model and token parameter");Require(context.Request.Url.AbsolutePath=="/chat/completions" && context.Request.Headers["Authorization"]=="Bearer FAKE-HTTP-KEY","custom request path and authentication");}byte[] bytes=Encoding.UTF8.GetBytes(reply);context.Response.ContentType="application/json";context.Response.ContentLength64=bytes.Length;context.Response.OutputStream.Write(bytes,0,bytes.Length);context.Response.Close();});
                await (Task)Call(form,"TestConnection");await serve;Require(n==0?state.Text.Contains("已验证"):state.Text.Contains("未通过"),n==0?"valid model text response accepted":"empty response removes prior success state");
            }
        }
        Require(!begin.Enabled,"verified model connection cannot unlock production takeover");
    }
    [STAThread]static int Main(string[] args){
        if(args.Length==1 && args[0]=="--live-readonly"){
            var value=new LiveBattleReader(Path.GetFullPath(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,".."))).Read();
            Console.WriteLine("Read-only: verified="+value.Verified+" fresh="+value.Fresh+" host_alive="+value.HostAlive+" can_stop="+value.CanStop);Console.WriteLine(value.Summary);Console.WriteLine(string.Join(Environment.NewLine,value.Checks));return 0;
        }
        Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);run=Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"test-runs",DateTime.Now.ToString("yyyyMMdd-HHmmss")+"-"+Guid.NewGuid().ToString("N").Substring(0,8));Directory.CreateDirectory(run);int code=0;
        try{StoreTests();LiveTests();}catch(Exception error){Console.Error.WriteLine("FAIL "+error);return 1;}
        var form=new CommanderHub(Path.Combine(run,"form")){ShowInTaskbar=false,Opacity=0};form.Shown+=async(s,e)=>{try{await FormTests(form);Console.WriteLine("ALL PASS "+checks+" checks; artifacts: "+run);}catch(Exception error){Console.Error.WriteLine("FAIL "+error);code=1;}finally{form.Close();}};Application.Run(form);return code;
    }
}
