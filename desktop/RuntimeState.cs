using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
using System.Web.Script.Serialization;

public class RuntimeBinding {public string session_id{get;set;}public string player_id{get;set;}public string commander_id{get;set;}public string commander_name{get;set;}public string connection_id{get;set;}public bool computer_verified{get;set;}}
public class RuntimeProvenance {public string kind{get;set;}public string description{get;set;}}
public class RuntimeSnapshot {public int snapshot_id{get;set;}public double game_time_seconds{get;set;}public bool paused{get;set;}}
public class RuntimePlan {public string plan_id{get;set;}public string stance{get;set;}public string production_focus{get;set;}public string economy_policy{get;set;}public string tech_policy{get;set;}public Dictionary<string,double> budget{get;set;}public string objective_region{get;set;}public string origin{get;set;}public double expires_at_game_seconds{get;set;}}
public class RuntimeResult {public string status{get;set;}public string reason_code{get;set;}}
public class RuntimeExecution {public bool enabled{get;set;}public bool dry_run{get;set;}public string reason_code{get;set;}}
public class RuntimeMetrics {public int requests{get;set;}public int accepted{get;set;}public int rejected{get;set;}public int timeouts{get;set;}public int plan_changes{get;set;}}
public class RuntimeStatus {
    public int schema_version{get;set;}public string service_state{get;set;}public string mode{get;set;}
    public RuntimeProvenance provenance{get;set;}public RuntimeBinding binding{get;set;}public RuntimeSnapshot latest_snapshot{get;set;}
    public RuntimePlan current_plan{get;set;}public RuntimeResult last_result{get;set;}public RuntimeExecution execution{get;set;}public RuntimeMetrics metrics{get;set;}
    public static RuntimeStatus Parse(string text){
        if(text==null || Encoding.UTF8.GetByteCount(text)>262144)throw new InvalidDataException("Status too large");
        var value=new JavaScriptSerializer().Deserialize<RuntimeStatus>(text);
        if(value==null || value.schema_version!=1 || value.mode!="simulation" || value.provenance==null || value.provenance.kind!="simulated" || value.binding==null || string.IsNullOrWhiteSpace(value.binding.session_id) || string.IsNullOrWhiteSpace(value.binding.player_id) || value.binding.computer_verified || value.execution==null || value.execution.enabled)throw new InvalidDataException("Only explicitly marked simulation status is currently supported");
        if(Array.IndexOf(new[]{"idle","planning","holding","fallback","stopped"},value.service_state)<0)throw new InvalidDataException("Unknown service state");
        if(value.latest_snapshot!=null && (value.latest_snapshot.snapshot_id<0 || !Finite(value.latest_snapshot.game_time_seconds) || value.latest_snapshot.game_time_seconds<0))throw new InvalidDataException("Invalid snapshot");
        if(value.metrics!=null && (value.metrics.requests<0 || value.metrics.accepted<0 || value.metrics.rejected<0 || value.metrics.timeouts<0 || value.metrics.plan_changes<0))throw new InvalidDataException("Invalid metrics");
        if(value.current_plan!=null && value.current_plan.budget!=null)foreach(var v in value.current_plan.budget.Values)if(!Finite(v) || v<0 || v>1)throw new InvalidDataException("Invalid budget");
        return value;
    }
    static bool Finite(double n){return !double.IsNaN(n) && !double.IsInfinity(n);}
    public static string Safe(string value){
        if(value==null)return "—";value=value.Replace("\r"," ").Replace("\n"," ");
        if(Regex.IsMatch(value,@"(?i)(api.?key|authorization|bearer\s|sk-[a-z0-9])"))return "[敏感内容已隐藏]";
        return value.Length>120?value.Substring(0,120)+"…":value;
    }
    public static RuntimeStatus Demo(CommanderProfile commander,int tick){
        return new RuntimeStatus{schema_version=1,mode="simulation",service_state=tick==0?"planning":"holding",provenance=new RuntimeProvenance{kind="simulated",description="本窗口离线演练；没有读取或控制真实游戏"},binding=new RuntimeBinding{session_id="offline-"+commander.id,player_id="sample-computer-3",commander_id=commander.id,commander_name=commander.name,connection_id=commander.connection_id,computer_verified=false},latest_snapshot=new RuntimeSnapshot{snapshot_id=tick,game_time_seconds=tick*5},current_plan=tick==0?null:new RuntimePlan{plan_id="offline-plan-1",stance="defend",production_focus="anti_air",economy_policy="hold",tech_policy="hold_current_tier",objective_region="sample-home",origin="local_fallback",expires_at_game_seconds=90,budget=new Dictionary<string,double>{{"economy",0.35},{"production",0.45},{"tech",0.1},{"reserve",0.1}}},last_result=new RuntimeResult{status=tick==0?"planning":"dry_run",reason_code=tick==0?"offline_sample_started":"production_control_not_verified"},execution=new RuntimeExecution{enabled=false,dry_run=true,reason_code="production_control_not_verified"},metrics=new RuntimeMetrics{requests=tick==0?0:1,accepted=tick==0?0:1,plan_changes=tick==0?0:1}};
    }
}
