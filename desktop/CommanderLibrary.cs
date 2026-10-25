using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;

public class ConnectionProfile {
    public string id {get;set;} public string name {get;set;} public string provider {get;set;} public string base_url {get;set;}
    public bool remember_key {get;set;} public string default_model {get;set;}
    [ScriptIgnore] public string key {get;set;}
    [ScriptIgnore] public int revision {get;set;}
    [ScriptIgnore] public bool credential_load_failed {get;set;}
    public override string ToString(){return name;}
}
public class CommanderProfile {
    public string id {get;set;} public string name {get;set;} public string connection_id {get;set;}
    public string model {get;set;} public int personality {get;set;} public string traits {get;set;}
    public override string ToString(){return name;}
}
public class CommanderLibraryDocument {
    public int schema_version {get;set;} public List<ConnectionProfile> connections {get;set;}
    public List<CommanderProfile> commanders {get;set;}
}
public class CommanderLibrary {
    public readonly string directory;
    public CommanderLibraryDocument Data;
    public bool MigratedLegacy {get;private set;}
    readonly JavaScriptSerializer json=new JavaScriptSerializer();
    public static readonly string[] TraitPresets={"主动侦察，优先早期施压和集中突破。保持必要防空与经济，不盲目冲击明显劣势战斗。","优先稳定经济、侦察和扩张，保留预备队；发现明确优势时主动进攻。","偏好多线骚扰、打击矿车与生产设施，利用机动兵力，避免无意义正面消耗。"};
    public CommanderLibrary(string directory){this.directory=directory;Load();}
    public ConnectionProfile AddConnection(string name,string provider,string url){
        var c=new ConnectionProfile{id=Guid.NewGuid().ToString("D"),name=name,provider=provider,base_url=url,key="",default_model=provider=="DeepSeek"?"deepseek-flash":""};Data.connections.Add(c);return c;
    }
    public CommanderProfile AddCommander(string name,ConnectionProfile connection,int personality){
        var c=new CommanderProfile{id=Guid.NewGuid().ToString("D"),name=name,connection_id=connection.id,model="",personality=personality,traits=TraitPresets[personality]};Data.commanders.Add(c);return c;
    }
    void Load(){
        string path=Path.Combine(directory,"library.v2.json");
        if(File.Exists(path)){
            if(new FileInfo(path).Length>1024*1024)throw new InvalidDataException("Library too large");
            Data=json.Deserialize<CommanderLibraryDocument>(File.ReadAllText(path,Encoding.UTF8));Validate();
            foreach(var c in Data.connections){
                c.key="";string secret=SecretPath(c.id);
                if(c.remember_key){
                    try{if(!File.Exists(secret) || new FileInfo(secret).Length>65536)throw new InvalidDataException();c.key=Encoding.UTF8.GetString(ProtectedData.Unprotect(File.ReadAllBytes(secret),null,DataProtectionScope.CurrentUser));}
                    catch{c.credential_load_failed=true;}
                }
            }
            return;
        }
        Data=new CommanderLibraryDocument{schema_version=2,connections=new List<ConnectionProfile>(),commanders=new List<CommanderProfile>()};
        string legacyPath=Path.Combine(directory,"config.json");
        if(File.Exists(legacyPath)){
            var legacy=json.Deserialize<Legacy>(File.ReadAllText(legacyPath,Encoding.UTF8));
            var connection=AddConnection("原有模型连接",legacy.provider??"自定义",legacy.base_url??"");
            var commander=AddCommander("原有指挥官",connection,Math.Max(0,Math.Min(2,legacy.personality)));
            connection.default_model=legacy.model??"";commander.model="";commander.traits=legacy.traits??commander.traits;
            string secret=Path.Combine(directory,"key.dpapi");
            if(File.Exists(secret)){connection.remember_key=true;try{if(new FileInfo(secret).Length>65536)throw new InvalidDataException();connection.key=Encoding.UTF8.GetString(ProtectedData.Unprotect(File.ReadAllBytes(secret),null,DataProtectionScope.CurrentUser));}catch{connection.credential_load_failed=true;}}
            MigratedLegacy=true;return;
        }
        var first=AddConnection("OpenAI 主连接","OpenAI","https://api.openai.com/v1");
        AddConnection("DeepSeek 主连接","DeepSeek","https://api.deepseek.com");
        AddCommander("铁锤",first,0);AddCommander("堡垒",first,1);AddCommander("幽灵",first,2);
    }
    public ConnectionProfile FindConnection(string id){return Data.connections.FirstOrDefault(c=>c.id==id);}
    public string EffectiveModel(CommanderProfile commander){var c=FindConnection(commander.connection_id);return !string.IsNullOrWhiteSpace(commander.model)?commander.model:(c==null?"":c.default_model??"");}
    public void Validate(){
        if(Data==null || Data.schema_version!=2 || Data.connections==null || Data.commanders==null || Data.connections.Count<1 || Data.connections.Count>100 || Data.commanders.Count<1 || Data.commanders.Count>100)throw new InvalidDataException("Invalid library schema");
        var ids=new HashSet<string>(StringComparer.OrdinalIgnoreCase);var names=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach(var c in Data.connections){Guid guid;if(c==null || !Guid.TryParse(c.id,out guid) || !ids.Add(c.id) || string.IsNullOrWhiteSpace(c.name) || c.name.Length>60 || !names.Add(c.name.Trim()) || (c.default_model??"").Length>200)throw new InvalidDataException("连接的名字与ID必须唯一且有效。");if(c.provider!="OpenAI" && c.provider!="DeepSeek" && c.provider!="自定义")throw new InvalidDataException("Unsupported provider");Uri uri;if(!TryEndpoint(c.base_url,out uri))throw new InvalidDataException("连接地址需要HTTPS，本机服务可使用HTTP基础地址。");}
        ids.Clear();names.Clear();
        foreach(var c in Data.commanders){Guid guid;if(c==null || !Guid.TryParse(c.id,out guid) || !ids.Add(c.id) || string.IsNullOrWhiteSpace(c.name) || c.name.Length>40 || !names.Add(c.name.Trim()) || FindConnection(c.connection_id)==null || c.personality<0 || c.personality>2 || (c.model??"").Length>200 || (c.traits??"").Length>4000)throw new InvalidDataException("指挥官名字与ID必须唯一，且需引用有效连接。");}
    }
    public static bool TryEndpoint(string address,out Uri uri){
        uri=null;string value=(address??"").Trim().TrimEnd('/');
        if(value.EndsWith("/chat/completions",StringComparison.OrdinalIgnoreCase))return false;
        return Uri.TryCreate(value+"/chat/completions",UriKind.Absolute,out uri) && (uri.Scheme=="https" || (uri.Scheme=="http" && uri.IsLoopback)) && string.IsNullOrEmpty(uri.UserInfo) && string.IsNullOrEmpty(uri.Query) && string.IsNullOrEmpty(uri.Fragment);
    }
    string SecretPath(string id){Guid parsed;if(!Guid.TryParse(id,out parsed))throw new InvalidDataException("Invalid connection ID");return Path.Combine(directory,"secrets",parsed.ToString("D")+".dpapi");}
    static void AtomicWrite(string path,byte[] bytes){string temp=path+".tmp-"+Guid.NewGuid().ToString("N");File.WriteAllBytes(temp,bytes);if(File.Exists(path))File.Replace(temp,path,null);else File.Move(temp,path);}
    public void Save(){
        Validate();Directory.CreateDirectory(directory);Directory.CreateDirectory(Path.Combine(directory,"secrets"));
        string document=json.Serialize(Data);
        // Keys are intentionally excluded by ScriptIgnore. Preserve legacy files.
        foreach(var c in Data.connections){string path=SecretPath(c.id);if(c.remember_key && !string.IsNullOrEmpty(c.key)){AtomicWrite(path,ProtectedData.Protect(Encoding.UTF8.GetBytes(c.key),null,DataProtectionScope.CurrentUser));c.credential_load_failed=false;}else if(c.credential_load_failed && c.remember_key){/* Keep unreadable original bytes until explicit re-entry or forget. */}else if(File.Exists(path))File.Delete(path);}
        AtomicWrite(Path.Combine(directory,"library.v2.json"),Encoding.UTF8.GetBytes(document));
        var exported=new {schema_version=1,game_sync_verified=false,instance_key=new[]{"session_id","player_id","commander_id"},commanders=Data.commanders.Select(c=>new{id=c.id,name=c.name,connection_id=c.connection_id,model_override=c.model,effective_model=EffectiveModel(c),personality=c.personality}).ToArray()};
        AtomicWrite(Path.Combine(directory,"commander-bindings.json"),Encoding.UTF8.GetBytes(json.Serialize(exported)));
    }
    class Legacy{public string provider{get;set;}public string base_url{get;set;}public string model{get;set;}public int personality{get;set;}public string traits{get;set;}}
}
