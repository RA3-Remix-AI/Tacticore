using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

class CommanderHub : Form {
    readonly Color ink=Color.FromArgb(226,218,191), muted=Color.FromArgb(154,151,137), gold=Color.FromArgb(205,169,94), surface=Color.FromArgb(28,30,29);
    readonly JavaScriptSerializer json=new JavaScriptSerializer();
    CommanderLibrary library;bool loadFailed,loading,dirty;ConnectionProfile currentConnection;CommanderProfile currentCommander;
    DarkComboBox connections=new DarkComboBox(),providers=new DarkComboBox(),commanders=new DarkComboBox(),profileConnection=new DarkComboBox(),personas=new DarkComboBox(),battleCommander=new DarkComboBox(),targets=new DarkComboBox();
    TextBox connectionName=Input(),endpoint=Input(),key=Input(),testModel=Input(),commanderName=Input(),model=Input(),traits=Input(),plan=Input(),feedback=Input(),log=Input();
    CheckBox remember=new CheckBox();Label modelState=new Label(),gameState=new Label(),profileState=new Label(),sourceState=new Label(),readiness=new Label();
    Button test,begin,stop;TacticalPanel identity=new TacticalPanel();
    HashSet<string> verifiedModels=new HashSet<string>();
    System.Windows.Forms.Timer watch=new System.Windows.Forms.Timer();string watchPath;bool demo;int demoTick;RuntimeStatus status;string lastStatusText;
    CancellationTokenSource requests=new CancellationTokenSource();
    static TextBox Input(){return new TextBox{BackColor=Color.FromArgb(17,21,19),ForeColor=Color.FromArgb(226,218,191),BorderStyle=BorderStyle.FixedSingle};}
    public CommanderHub(string directory){
        Text="三极战线 · 指挥官控制台 / 验收版";ClientSize=new Size(1120,850);MinimumSize=new Size(1080,840);AutoScaleMode=AutoScaleMode.None;
        BackColor=Color.FromArgb(14,16,15);ForeColor=ink;Font=new Font("Microsoft YaHei UI",10);StartPosition=FormStartPosition.CenterScreen;
        try{library=new CommanderLibrary(directory);}catch{loadFailed=true;library=new CommanderLibrary(Path.Combine(Path.GetTempPath(),"TriadFrontCommander-recovery-"+Guid.NewGuid().ToString("N")));}
        var shell=new TableLayoutPanel{Dock=DockStyle.Fill,Padding=new Padding(22),ColumnCount=2,RowCount=2};
        shell.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,250));shell.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));shell.RowStyles.Add(new RowStyle(SizeType.Absolute,92));shell.RowStyles.Add(new RowStyle(SizeType.Percent,100));
        var header=new TacticalPanel{Dock=DockStyle.Fill,Header=true};shell.Controls.Add(header,0,0);shell.SetColumnSpan(header,2);
        identity.Dock=DockStyle.Fill;identity.Margin=new Padding(0,12,16,0);shell.Controls.Add(identity,0,1);
        var tabs=new DarkTabControl{Dock=DockStyle.Fill,Margin=new Padding(0,12,0,0)};
        tabs.AddTab("01  模型连接库",ConnectionPage());
        tabs.AddTab("02  指挥官档案",CommanderPage());
        tabs.AddTab("03  战局与日志",BattlePage());
        tabs.AddTab("04  实时战局",new LiveBattlePage(Path.GetFullPath(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"..")),Path.Combine(directory,"library.v2.json"),()=>library.Data.commanders,()=>dirty || loadFailed));
        shell.Controls.Add(tabs,1,1);Controls.Add(shell);
        watch.Interval=1000;watch.Tick+=(s,e)=>WatchTick();FormClosing+=(s,e)=>{watch.Stop();requests.Cancel();};
        dirty=library.MigratedLegacy || !File.Exists(Path.Combine(directory,"library.v2.json"));
        RefreshLists();SelectConnection(library.Data.connections[0]);SelectCommander(library.Data.commanders[0]);RenderStatus();
        Write(loadFailed?"配置读取失败：原文件已保留。当前为只读恢复视图，不会覆盖现有配置。":library.MigratedLegacy?"已只读迁移旧配置到内存。显式保存后写入新库；旧配置和旧密钥文件保留。":"连接可复用；每位指挥官拥有独立名字、模型与性格。改名不改变绑定ID。");
        Write("真实宿主遥测与启动条件请在实时战局页核验；离线演练不读取或控制游戏。");UpdateStates();
    }
    TableLayoutPanel Grid(params float[] heights){
        var panel=new TableLayoutPanel{Dock=DockStyle.Fill,Padding=new Padding(18),ColumnCount=2,RowCount=heights.Length,BackColor=surface};
        panel.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,112));panel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));
        foreach(float height in heights)panel.RowStyles.Add(height<0?new RowStyle(SizeType.Percent,100):new RowStyle(SizeType.Absolute,height));return panel;
    }
    void Row(TableLayoutPanel panel,int row,string title,Control control){panel.Controls.Add(new Label{Text=title,ForeColor=muted,Dock=DockStyle.Fill,TextAlign=ContentAlignment.MiddleLeft},0,row);control.Dock=DockStyle.Fill;control.Margin=new Padding(0,7,0,5);panel.Controls.Add(control,1,row);}
    void Span(TableLayoutPanel panel,int row,Control control){control.Dock=DockStyle.Fill;panel.Controls.Add(control,0,row);panel.SetColumnSpan(control,2);}
    Label Note(string text){return new Label{Text=text,ForeColor=muted,Dock=DockStyle.Fill,AutoEllipsis=true};}
    Button Action(string text,int width,bool primary=false){return new DarkButton{Text=text,Primary=primary,Width=width,Height=36,ForeColor=ink,Margin=new Padding(0,4,10,4)};}
    Control ConnectionPage(){
        var p=Grid(44,44,44,44,44,44,32,48,36,56,-1);
        providers.Items.AddRange(new string[]{"OpenAI","DeepSeek","自定义"});key.UseSystemPasswordChar=true;
        Row(p,0,"已保存连接",connections);Row(p,1,"连接名称",connectionName);Row(p,2,"供应商",providers);Row(p,3,"基础地址",endpoint);Row(p,4,"API Key",key);Row(p,5,"默认模型",testModel);
        remember.Text="按当前 Windows 用户加密保存此连接的密钥";remember.ForeColor=muted;remember.AutoSize=true;Span(p,6,remember);
        var actions=new FlowLayoutPanel{Dock=DockStyle.Fill};var add=Action("新增连接",108);var save=Action("保存连接库",120);test=Action("测试连接",114,true);
        add.Click+=(s,e)=>{CaptureConnection();var item=library.AddConnection(UniqueName("新连接",library.Data.connections.Select(c=>c.name)),"OpenAI","https://api.openai.com/v1");MarkDirty();RefreshLists();SelectConnection(item);};save.Click+=(s,e)=>Save();save.Enabled=!loadFailed;test.Click+=async(s,e)=>await TestConnection();actions.Controls.AddRange(new Control[]{add,save,test});Span(p,7,actions);
        Span(p,8,modelState);Span(p,9,Note("多个档案继承此默认模型；档案可单独覆盖。测试会发送一次简短请求，可能产生费用。切换供应商会清空本连接密钥。"));
        log.Multiline=true;log.ReadOnly=true;log.ScrollBars=ScrollBars.Vertical;log.ForeColor=Color.FromArgb(163,181,151);Span(p,10,log);
        connections.SelectedIndexChanged+=(s,e)=>{if(!loading && connections.SelectedItem!=null){CaptureConnection();SelectConnection((ConnectionProfile)connections.SelectedItem);}};
        connectionName.TextChanged+=(s,e)=>{if(!loading){CaptureConnection();MarkDirty();connections.Refresh();profileConnection.Refresh();}};
        providers.SelectedIndexChanged+=(s,e)=>{if(loading || currentConnection==null)return;loading=true;key.Clear();remember.Checked=false;endpoint.Text=providers.SelectedIndex==0?"https://api.openai.com/v1":providers.SelectedIndex==1?"https://api.deepseek.com":"";testModel.Text=providers.SelectedIndex==1?"deepseek-flash":"";endpoint.ReadOnly=providers.SelectedIndex!=2;loading=false;CaptureConnection();InvalidateConnection();MarkDirty();Write("此连接供应商已改变，密钥已从编辑器清空；其他连接的密钥不受影响。");};
        endpoint.TextChanged+=(s,e)=>{if(!loading){CaptureConnection();InvalidateConnection();MarkDirty();}};key.TextChanged+=(s,e)=>{if(!loading){CaptureConnection();InvalidateConnection();MarkDirty();}};remember.CheckedChanged+=(s,e)=>{if(!loading){CaptureConnection();MarkDirty();}};testModel.TextChanged+=(s,e)=>{if(!loading){CaptureConnection();MarkDirty();}};return p;
    }
    Control CommanderPage(){
        var p=Grid(44,44,44,44,44,104,48,80,74,-1);
        personas.Items.AddRange(new string[]{"突击 / 集中突破","经营 / 稳定发展","游击 / 机动骚扰"});traits.Multiline=true;traits.ScrollBars=ScrollBars.Vertical;traits.MaxLength=4000;commanderName.MaxLength=40;model.MaxLength=200;
        Row(p,0,"指挥官档案",commanders);Row(p,1,"游戏显示名",commanderName);Row(p,2,"复用连接",profileConnection);Row(p,3,"模型覆盖",model);Row(p,4,"性格预设",personas);Row(p,5,"性格与偏好",traits);
        var actions=new FlowLayoutPanel();var add=Action("新增指挥官",125);var save=Action("保存所有档案",140,true);add.Click+=(s,e)=>{CaptureCommander();var item=library.AddCommander(UniqueName("新指挥官",library.Data.commanders.Select(c=>c.name)),currentConnection??library.Data.connections[0],0);MarkDirty();RefreshLists();SelectCommander(item);};save.Click+=(s,e)=>Save();save.Enabled=!loadFailed;actions.Controls.AddRange(new Control[]{add,save});Span(p,6,actions);
        Span(p,7,profileState);Span(p,8,Note("模型覆盖留空即继承连接默认模型。多个档案可共享连接；名字可改，UUID 不变。游戏注册与绑定以实时战局页当前会话核验为准。"));
        Span(p,9,Note("本地保存会同时导出无密钥 commander-bindings.json，供后续游戏注册与会话绑定使用。"));
        commanders.SelectedIndexChanged+=(s,e)=>{if(!loading && commanders.SelectedItem!=null){CaptureCommander();SelectCommander((CommanderProfile)commanders.SelectedItem);}};
        commanderName.TextChanged+=(s,e)=>{if(!loading){CaptureCommander();MarkDirty();commanders.Refresh();battleCommander.Refresh();identity.CommanderName=commanderName.Text;identity.Invalidate();}};
        profileConnection.SelectedIndexChanged+=(s,e)=>{if(!loading){CaptureCommander();MarkDirty();}};model.TextChanged+=(s,e)=>{if(!loading){CaptureCommander();MarkDirty();}};
        traits.TextChanged+=(s,e)=>{if(!loading){CaptureCommander();MarkDirty();}};personas.SelectedIndexChanged+=(s,e)=>{if(!loading && personas.SelectedIndex>=0){traits.Text=CommanderLibrary.TraitPresets[personas.SelectedIndex];CaptureCommander();identity.Personality=personas.SelectedIndex;identity.Invalidate();MarkDirty();}};return p;
    }
    Control BattlePage(){
        var p=Grid(44,48,60,44,48,80,24,126,24,-1);
        Row(p,0,"本地指挥官",battleCommander);
        var imports=new FlowLayoutPanel();var open=Action("载入策略状态",140);var offline=Action("离线演练",125);open.Click+=(s,e)=>ImportStatus();offline.Click+=(s,e)=>StartDemo();imports.Controls.AddRange(new Control[]{open,offline});Span(p,1,imports);
        sourceState.Text="来源：未加载。真实电脑名单尚未识别；没有自动选中任何游戏玩家。";sourceState.ForeColor=muted;Span(p,2,sourceState);Row(p,3,"目标电脑玩家",targets);
        var actions=new FlowLayoutPanel();begin=Action("真实指挥尚未就绪",150);begin.Enabled=false;stop=Action("停止本地观察",150);stop.Enabled=false;stop.Click+=(s,e)=>StopLocal();var detect=Action("检测游戏桥接",140);detect.Click+=async(s,e)=>{detect.Enabled=false;try{await DetectGame();}finally{detect.Enabled=true;}};actions.Controls.AddRange(new Control[]{begin,stop,detect});Span(p,4,actions);
        readiness.ForeColor=muted;Span(p,5,readiness);Span(p,6,Note("当前计划 / 仅展示，不下达游戏命令"));plan.Multiline=true;plan.ReadOnly=true;plan.ScrollBars=ScrollBars.Vertical;Span(p,7,plan);Span(p,8,Note("执行反馈与验收计数"));feedback.Multiline=true;feedback.ReadOnly=true;feedback.ScrollBars=ScrollBars.Vertical;Span(p,9,feedback);
        battleCommander.SelectedIndexChanged+=(s,e)=>{if(!loading && battleCommander.SelectedItem!=null){CaptureCommander();SelectCommander((CommanderProfile)battleCommander.SelectedItem);if(demo)StopLocal();RenderStatus();}};targets.Enabled=false;return p;
    }
    static string UniqueName(string prefix,IEnumerable<string> existing){var names=new HashSet<string>(existing,StringComparer.OrdinalIgnoreCase);for(int n=1;;n++){string name=prefix+" "+n;if(!names.Contains(name))return name;}}
    void RefreshLists(){bool before=loading;loading=true;connections.Items.Clear();profileConnection.Items.Clear();commanders.Items.Clear();battleCommander.Items.Clear();foreach(var c in library.Data.connections){connections.Items.Add(c);profileConnection.Items.Add(c);}foreach(var c in library.Data.commanders){commanders.Items.Add(c);battleCommander.Items.Add(c);}if(currentConnection!=null)connections.SelectedItem=currentConnection;if(currentCommander!=null){commanders.SelectedItem=currentCommander;battleCommander.SelectedItem=currentCommander;profileConnection.SelectedItem=library.FindConnection(currentCommander.connection_id);}loading=before;}
    void SelectConnection(ConnectionProfile c){bool before=loading;loading=true;currentConnection=c;connections.SelectedItem=c;connectionName.Text=c.name;providers.SelectedItem=c.provider;endpoint.Text=c.base_url;endpoint.ReadOnly=c.provider!="自定义";key.Text=c.key??"";remember.Checked=c.remember_key;testModel.Text=c.default_model??"";loading=before;UpdateStates();if(c.credential_load_failed)Write("此连接的本机密钥无法读取，需要重新填写。原库、原密钥文件及其他连接已保留。");}
    void SelectCommander(CommanderProfile c){bool before=loading;loading=true;currentCommander=c;commanders.SelectedItem=c;battleCommander.SelectedItem=c;commanderName.Text=c.name;profileConnection.SelectedItem=library.FindConnection(c.connection_id);model.Text=c.model??"";personas.SelectedIndex=c.personality;traits.Text=c.traits??"";identity.Personality=c.personality;identity.CommanderName=c.name;identity.Invalidate();loading=before;UpdateStates();}
    void CaptureConnection(){if(currentConnection==null || loading)return;currentConnection.name=connectionName.Text.Trim();currentConnection.provider=providers.Text;currentConnection.base_url=endpoint.Text.Trim();currentConnection.key=key.Text;currentConnection.remember_key=remember.Checked;currentConnection.default_model=testModel.Text.Trim();}
    void CaptureCommander(){if(currentCommander==null || loading)return;currentCommander.name=commanderName.Text.Trim();var c=profileConnection.SelectedItem as ConnectionProfile;if(c!=null)currentCommander.connection_id=c.id;currentCommander.model=model.Text.Trim();currentCommander.personality=Math.Max(0,personas.SelectedIndex);currentCommander.traits=traits.Text;}
    void MarkDirty(){dirty=true;UpdateStates();}
    void InvalidateConnection(){if(currentConnection!=null){currentConnection.revision++;verifiedModels.RemoveWhere(s=>s.StartsWith(currentConnection.id+"|",StringComparison.Ordinal));}UpdateStates();}
    void UpdateStates(){
        if(currentConnection!=null)modelState.Text=currentConnection.credential_load_failed && string.IsNullOrEmpty(currentConnection.key)?"● 此连接密钥无法读取，需要重填；原文件已保留":verifiedModels.Contains(currentConnection.id+"|"+testModel.Text.Trim())?"● 此连接的默认模型已验证；覆盖模型需单独验证":"● 此连接未验证 / 请填写默认模型";
        if(currentCommander!=null){var c=library.FindConnection(currentCommander.connection_id);bool complete=c!=null && !string.IsNullOrWhiteSpace(library.EffectiveModel(currentCommander)) && (!string.IsNullOrWhiteSpace(c.key) || IsLocal(c.base_url));profileState.Text="本地："+(loadFailed?"只读恢复":dirty?"有未保存更改":"已保存")+"   |   游戏注册 / 绑定：见实时战局核验\n桌面启动：先检查当前会话条件"+(complete?"":"   |   模型或密钥未配置")+"\n实际模型："+RuntimeStatus.Safe(library.EffectiveModel(currentCommander))+(string.IsNullOrWhiteSpace(currentCommander.model)?"（继承）":"（档案覆盖）");}
        if(begin!=null)begin.Enabled=false;
        if(readiness!=null)readiness.Text="此页仅离线演练。真实宿主状态与启动条件请在实时战局页核验。\n模型连接通过只代表端点可用。"+(gameState.Text??"");
    }
    static bool IsLocal(string address){Uri u;return Uri.TryCreate(address,UriKind.Absolute,out u)&&u.IsLoopback;}
    void Save(){CaptureConnection();CaptureCommander();if(loadFailed){Write("恢复视图禁止覆盖原配置。");return;}try{library.Save();dirty=false;UpdateStates();profileState.Text=profileState.Text.Replace("已载入 / 可保存","已保存");Write("连接库与指挥官档案已保存，已导出无密钥绑定表。游戏状态请见实时战局页当前会话核验。");}catch(InvalidDataException error){Write(error.Message);}catch{Write("保存失败；请检查配置目录。没有写入明文密钥。");}}
    void Write(string text){if(!IsDisposed)log.AppendText(DateTime.Now.ToString("HH:mm:ss")+"  "+text+Environment.NewLine+Environment.NewLine);}
    async Task TestConnection(){
        CaptureConnection();if(currentConnection==null)return;Uri uri;if(!CommanderLibrary.TryEndpoint(currentConnection.base_url,out uri)){Write("请填写有效基础地址：HTTPS，或本机HTTP；不要填写完整请求路径。");return;}string selectedModel=testModel.Text.Trim();if(selectedModel.Length==0){Write("请填写测试模型；测试不会改变指挥官档案。");return;}if(!IsLocal(currentConnection.base_url)&&string.IsNullOrWhiteSpace(currentConnection.key)){Write("此云端连接尚未填写密钥。");return;}
        var c=currentConnection;int revision=c.revision;bool passed=false;test.Enabled=false;modelState.Text="● 正在验证此连接……";verifiedModels.Remove(c.id+"|"+selectedModel);
        try{using(var handler=new HttpClientHandler{AllowAutoRedirect=false})using(var client=new HttpClient(handler)){
            client.Timeout=TimeSpan.FromSeconds(25);var request=new HttpRequestMessage(HttpMethod.Post,uri);if(!string.IsNullOrWhiteSpace(c.key))request.Headers.Authorization=new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer",c.key.Trim());
            var body=new Dictionary<string,object>{{"model",selectedModel},{"messages",new[]{new{role="user",content="Connection test. Reply only OK."}}},{"stream",false}};body[c.provider=="OpenAI"?"max_completion_tokens":"max_tokens"]=128;request.Content=new StringContent(json.Serialize(body),Encoding.UTF8,"application/json");
            using(var response=await client.SendAsync(request,requests.Token)){if(!response.IsSuccessStatusCode){Write("连接测试未通过，HTTP "+(int)response.StatusCode+"；请检查端点、模型与认证。");return;}string text=await response.Content.ReadAsStringAsync();if(text.Length>1024*1024){Write("响应过大，未通过验证。");return;}var parsed=json.DeserializeObject(text) as Dictionary<string,object>;var choices=parsed!=null&&parsed.ContainsKey("choices")?parsed["choices"] as object[]:null;var first=choices!=null&&choices.Length>0?choices[0] as Dictionary<string,object>:null;var message=first!=null&&first.ContainsKey("message")?first["message"] as Dictionary<string,object>:null;if(message==null||!message.ContainsKey("content")||string.IsNullOrWhiteSpace(message["content"] as string)){Write("未返回有效文本，连接测试未通过。");return;}if(c.revision!=revision){Write("请求结束但连接已变更，结果已丢弃。");return;}passed=true;verifiedModels.Add(c.id+"|"+selectedModel);Write("连接测试通过；尚未注册或接管游戏指挥官。");}
        }}catch(TaskCanceledException){Write("连接测试取消或超时。");}catch{Write("请求失败；响应正文、密钥和认证头不会写入日志。");}finally{if(!IsDisposed){test.Enabled=true;UpdateStates();if(!passed && currentConnection==c)modelState.Text="● 此连接的测试未通过";}}
    }
    void ImportStatus(){using(var dialog=new OpenFileDialog{Filter="策略状态 JSON|*.json",Title="载入只读策略状态（当前仅支持明确标记的模拟状态）"}){if(dialog.ShowDialog(this)!=DialogResult.OK)return;try{ReadStatus(dialog.FileName);watch.Stop();watchPath=dialog.FileName;demo=false;watch.Start();stop.Enabled=true;stop.Text="停止本地观察";Write("已载入只读模拟状态。停止只结束本窗口观察，不停止外部服务。");}catch{Write("状态未载入：只接受有效、明确标记且执行关闭的模拟状态。");}}}
    void ReadStatus(string path){if(new FileInfo(path).Length>262144)throw new InvalidDataException();string raw=File.ReadAllText(path,Encoding.UTF8);status=RuntimeStatus.Parse(raw);if(raw!=lastStatusText){lastStatusText=raw;RenderStatus();}}
    void StartDemo(){if(currentCommander==null)return;watch.Stop();watchPath=null;demo=true;demoTick=0;status=RuntimeStatus.Demo(currentCommander,0);lastStatusText=null;watch.Start();stop.Enabled=true;stop.Text="停止离线演练";RenderStatus();Write("已开始本窗口离线演练：无模型请求、无游戏读取、无游戏命令。");}
    void WatchTick(){try{if(demo){demoTick++;status=RuntimeStatus.Demo(currentCommander,demoTick);RenderStatus();}else if(watchPath!=null)ReadStatus(watchPath);}catch{watch.Stop();stop.Enabled=false;sourceState.Text="状态读取失败，已停止本地观察；没有发出游戏命令。";Write("状态文件无法继续读取，当前观察已停止。");}}
    void StopLocal(){watch.Stop();bool wasDemo=demo;demo=false;watchPath=null;stop.Enabled=false;if(status!=null && wasDemo){status.service_state="stopped";status.last_result=new RuntimeResult{status="stopped",reason_code="local_demo_stopped"};RenderStatus();}else sourceState.Text="已停止本窗口观察；外部服务与游戏没有被停止。";Write(wasDemo?"离线演练已停止；没有停止任何游戏进程。":"已停止本地观察；没有停止外部服务或游戏。");}
    void RenderStatus(){
        targets.Items.Clear();targets.Enabled=false;
        if(status==null){sourceState.Text="来源：未加载；未收到已核验真实电脑名单。";plan.Text="尚无计划。";feedback.Text="真实执行器未接入。";return;}
        bool matched=currentCommander!=null && status.binding.commander_id==currentCommander.id && status.binding.connection_id==currentCommander.connection_id;
        sourceState.Text="来源：模拟 / 离线样例；不代表真实电脑玩家。\n档案："+(matched?"离线样例匹配当前 UUID":"未匹配当前档案 UUID，仅展示")+"；状态："+RuntimeStatus.Safe(status.service_state);
        targets.Items.Add("离线样例 / "+RuntimeStatus.Safe(status.binding.player_id)+"（非真实电脑识别）");targets.SelectedIndex=0;
        var p=status.current_plan;
        plan.Text=p==null?"尚无计划。":string.Format("计划：{0}  /  来源：{1}\r\n姿态：{2}    生产方向：{3}\r\n经济：{4}    科技：{5}\r\n目标区域：{6}\r\n预算：{7}",RuntimeStatus.Safe(p.plan_id),RuntimeStatus.Safe(p.origin),RuntimeStatus.Safe(p.stance),RuntimeStatus.Safe(p.production_focus),RuntimeStatus.Safe(p.economy_policy),RuntimeStatus.Safe(p.tech_policy),RuntimeStatus.Safe(p.objective_region),p.budget==null?"—":string.Join(" / ",p.budget.Select(x=>RuntimeStatus.Safe(x.Key)+" "+x.Value.ToString("P0"))));
        var m=status.metrics;feedback.Text="执行关闭 / dry-run；没有向游戏发送命令。\r\n"+(status.last_result==null?"暂无反馈":RuntimeStatus.Safe(status.last_result.status)+" / "+RuntimeStatus.Safe(status.last_result.reason_code))+"\r\n"+(m==null?"暂无计数":string.Format("请求 {0}  接受 {1}  拒绝 {2}  超时 {3}  计划变更 {4}",m.requests,m.accepted,m.rejected,m.timeouts,m.plan_changes));UpdateStates();
    }
    async Task DetectGame(){
        var processes=Process.GetProcessesByName("ra3_1.12.game");if(processes.Length!=1){gameState.Text=" 游戏：未找到唯一游戏进程。";UpdateStates();return;}
        try{string path=processes[0].MainModule.FileName;using(var sha=SHA256.Create())using(var stream=File.OpenRead(path)){if(BitConverter.ToString(sha.ComputeHash(stream)).Replace("-","").ToLowerInvariant()!="ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165"){gameState.Text=" 游戏：不支持的文件版本。";UpdateStates();return;}}
            int pid=processes[0].Id;string exe=Path.GetFullPath(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"..","bin","controller.exe"));bool ok=await Task.Run(()=>{using(var p=Process.Start(new ProcessStartInfo(exe,pid+" ping"){UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true})){if(!p.WaitForExit(12000)){p.Kill();return false;}return p.ExitCode==0;}});gameState.Text=ok?" 游戏：窗口线程回调通过；尚未绑定电脑。":" 游戏：回调未通过。";
        }catch{gameState.Text=" 游戏：检测失败。";}UpdateStates();Write(gameState.Text);
    }
    [STAThread]static void Main(string[] args){Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);string folder=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"TriadFrontCommander");var form=new CommanderHub(folder);if(args.Length==1&&args[0]=="--smoke"){var t=new System.Windows.Forms.Timer{Interval=1000};t.Tick+=(s,e)=>form.Close();t.Start();}Application.Run(form);}
}
