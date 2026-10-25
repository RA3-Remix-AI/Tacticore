using System;
using System.Drawing;
using System.IO;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using System.Diagnostics;
using System.Drawing.Drawing2D;

class CommanderDesktop : Form {
    TextBox endpoint=new TextBox(), model=new TextBox(), key=new TextBox(), traits=new TextBox(), log=new TextBox();
    ComboBox persona=new ComboBox(); CheckBox remember=new CheckBox(); Button test=new Button();
    ComboBox provider=new ComboBox();
    Label modelStatus=new Label(),gameStatus=new Label();
    TacticalPanel identity=new TacticalPanel();
    int configRevision=0;
    Color ink=Color.FromArgb(226,218,191), muted=Color.FromArgb(154,151,137), red=Color.FromArgb(173,37,33), surface=Color.FromArgb(28,30,29);
    string folder=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"TriadFrontCommander");
    JavaScriptSerializer json=new JavaScriptSerializer();
    string[] names={"突击指挥官","经营指挥官","游击指挥官"};
    string[] profiles={"主动侦察，优先早期施压和集中突破。保持必要防空与经济，不盲目冲击明显劣势战斗。", "优先稳定经济、侦察和扩张，保留预备队；发现明确优势时主动进攻。", "偏好多线骚扰、打击矿车与生产设施，利用机动兵力，避免无意义正面消耗。"};
    void Row(TableLayoutPanel grid,string title,Control input,int row) {
        grid.RowStyles.Add(new RowStyle(SizeType.Absolute,row==5?88:44));
        var label=new Label{Text=title,Dock=DockStyle.Fill,TextAlign=ContentAlignment.MiddleLeft,ForeColor=muted};
        input.Dock=DockStyle.Fill; input.Margin=new Padding(0,8,0,5);
        input.BackColor=Color.FromArgb(18,20,19);input.ForeColor=ink;
        var textbox=input as TextBox;if(textbox!=null)textbox.BorderStyle=BorderStyle.FixedSingle;
        var combo=input as ComboBox;if(combo!=null)combo.FlatStyle=FlatStyle.Flat;
        grid.Controls.Add(label,0,row);grid.Controls.Add(input,1,row);
    }
    Button Action(string text,int width,bool primary) {
        var button=new Button{Text=text,Width=width,Height=38,FlatStyle=FlatStyle.Flat,BackColor=primary?red:surface,ForeColor=ink,Cursor=Cursors.Hand,Margin=new Padding(0,4,10,4)};
        button.FlatAppearance.BorderColor=primary?Color.FromArgb(224,79,51):Color.FromArgb(83,81,67);
        button.FlatAppearance.MouseOverBackColor=Color.FromArgb(110,35,28);return button;
    }
    CommanderDesktop() {
        Text="三极战线 · 战术指挥终端";ClientSize=new Size(1080,820);MinimumSize=new Size(1030,820);
        AutoScaleMode=AutoScaleMode.None;BackColor=Color.FromArgb(14,16,15);ForeColor=ink;
        Font=new Font("Microsoft YaHei UI",10);StartPosition=FormStartPosition.CenterScreen;
        var shell=new TableLayoutPanel{Dock=DockStyle.Fill,Padding=new Padding(22),ColumnCount=2,RowCount=2};
        shell.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,250));shell.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));
        shell.RowStyles.Add(new RowStyle(SizeType.Absolute,92));shell.RowStyles.Add(new RowStyle(SizeType.Percent,100));
        var header=new TacticalPanel{Dock=DockStyle.Fill,Header=true};shell.Controls.Add(header,0,0);shell.SetColumnSpan(header,2);
        identity.Dock=DockStyle.Fill;identity.Margin=new Padding(0,12,16,0);shell.Controls.Add(identity,0,1);
        var root=new TableLayoutPanel{Dock=DockStyle.Fill,Padding=new Padding(18,12,18,12),BackColor=surface,ColumnCount=1,RowCount=6,Margin=new Padding(0,12,0,0)};
        root.RowStyles.Add(new RowStyle(SizeType.Absolute,30));root.RowStyles.Add(new RowStyle(SizeType.Absolute,314));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute,34));root.RowStyles.Add(new RowStyle(SizeType.Absolute,51));root.RowStyles.Add(new RowStyle(SizeType.Absolute,56));root.RowStyles.Add(new RowStyle(SizeType.Percent,100));
        root.Controls.Add(new Label{Text="01  /  指挥链路配置",ForeColor=Color.FromArgb(205,169,94),Dock=DockStyle.Fill,Font=new Font(Font,FontStyle.Bold)},0,0);
        var grid=new TableLayoutPanel{Dock=DockStyle.Fill,ColumnCount=2,RowCount=6};
        grid.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,110));grid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));
        provider.DropDownStyle=ComboBoxStyle.DropDownList;provider.Items.AddRange(new string[]{"OpenAI","DeepSeek","自定义"});provider.SelectedIndex=0;
        endpoint.Text="https://api.openai.com/v1";model.Text="";key.UseSystemPasswordChar=true;
        persona.DropDownStyle=ComboBoxStyle.DropDownList;persona.Items.AddRange(names);persona.SelectedIndex=0;
        traits.Multiline=true;traits.ScrollBars=ScrollBars.Vertical;traits.Text=profiles[0];
        persona.SelectedIndexChanged+=(s,e)=>{traits.Text=profiles[persona.SelectedIndex];identity.Personality=persona.SelectedIndex;identity.Invalidate();};
        provider.SelectedIndexChanged+=(s,e)=>{
            key.Clear();
            if(provider.SelectedIndex==0){endpoint.Text="https://api.openai.com/v1";model.Clear();}
            else if(provider.SelectedIndex==1){endpoint.Text="https://api.deepseek.com";model.Text="deepseek-flash";}
            else{endpoint.Clear();model.Clear();}
            endpoint.ReadOnly=provider.SelectedIndex!=2;
            Write("服务已切换，请填写此服务的密钥与可用模型。密钥不会跨服务复用。");
        };
        endpoint.ReadOnly=true;
        Row(grid,"模型服务",provider,0);Row(grid,"基础地址",endpoint,1);Row(grid,"模型名称",model,2);Row(grid,"API Key",key,3);Row(grid,"指挥官",persona,4);Row(grid,"性格与偏好",traits,5);
        root.Controls.Add(grid,0,1);
        remember.Text="在本机加密保存 API Key";remember.AutoSize=true;remember.ForeColor=muted;remember.Padding=new Padding(105,0,0,0);root.Controls.Add(remember,0,2);
        var actions=new FlowLayoutPanel{Dock=DockStyle.Fill};
        var save=Action("保存配置",105,false);save.Click+=(s,e)=>Save();
        test=Action("测试模型连接",140,true);test.Click+=async(s,e)=>await Test();
        var detect=Action("检测游戏桥接",140,false);detect.Click+=async(s,e)=>{detect.Enabled=false;try{await DetectGame();}finally{detect.Enabled=true;}};
        actions.Controls.Add(save);actions.Controls.Add(test);actions.Controls.Add(detect);root.Controls.Add(actions,0,3);
        var status=new TableLayoutPanel{Dock=DockStyle.Fill,ColumnCount=1,RowCount=2};
        modelStatus.Text="● 模型链路：未验证";gameStatus.Text="● 游戏链路：未检测  /  战略接管未接入";
        modelStatus.Dock=gameStatus.Dock=DockStyle.Fill;modelStatus.ForeColor=gameStatus.ForeColor=muted;
        status.Controls.Add(modelStatus,0,0);status.Controls.Add(gameStatus,0,1);root.Controls.Add(status,0,4);
        log.Multiline=true;log.ReadOnly=true;log.ScrollBars=ScrollBars.Vertical;log.Dock=DockStyle.Fill;log.BackColor=Color.FromArgb(13,17,14);log.ForeColor=Color.FromArgb(163,181,151);log.BorderStyle=BorderStyle.FixedSingle;log.Font=new Font("Microsoft YaHei UI",9);
        root.Controls.Add(log,0,5);shell.Controls.Add(root,1,1);Controls.Add(shell);LoadConfig();
        endpoint.TextChanged+=(s,e)=>InvalidateModel();model.TextChanged+=(s,e)=>InvalidateModel();key.TextChanged+=(s,e)=>InvalidateModel();
        Write("终端就绪。连接测试会发送一次简短模型请求，可能产生费用。");
        Write("遭遇战的 AI 指挥官入口正在联调；模型验证、桥接回调与战略接管为三个独立状态。");
    }
    void InvalidateModel(){configRevision++;modelStatus.Text="● 模型链路：配置已变更，请重新验证";modelStatus.ForeColor=muted;}
    async Task DetectGame(){
        var processes=Process.GetProcessesByName("ra3_1.12.game");
        if(processes.Length!=1){gameStatus.Text="● 游戏链路：未找到唯一游戏进程";return;}
        try{
            string path=processes[0].MainModule.FileName;
            using(var sha=SHA256.Create())using(var stream=File.OpenRead(path)){
                if(BitConverter.ToString(sha.ComputeHash(stream)).Replace("-","").ToLowerInvariant()!="ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165") {gameStatus.Text="● 游戏链路：不支持的游戏版本";return;}
            }
            string exe=Path.GetFullPath(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"..","bin","controller.exe"));
            int pid=processes[0].Id;
            var result=await Task.Run(()=>{
                var start=new ProcessStartInfo(exe,pid+" ping"){UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true};
                using(var p=Process.Start(start)){if(!p.WaitForExit(12000)){p.Kill();return false;}return p.ExitCode==0;}
            });
            gameStatus.Text=result?"● 游戏链路：回调通过  /  战略接管未接入":"● 游戏链路：回调失败";
            Write(result?"游戏桥接回调通过；尚未启用模型自动指挥。":"游戏桥接未通过，请检查窗口与游戏版本。");
        }catch{gameStatus.Text="● 游戏链路：检测失败";}
    }
    void Write(string message){log.AppendText(DateTime.Now.ToString("HH:mm:ss")+"  "+message+Environment.NewLine+Environment.NewLine);}
    void LoadConfig(){
        try {
            var path=Path.Combine(folder,"config.json");if(!File.Exists(path))return;
            var cfg=json.Deserialize<Settings>(File.ReadAllText(path,Encoding.UTF8));
            provider.SelectedIndex=cfg.provider=="DeepSeek"?1:cfg.provider=="OpenAI"?0:2;
            endpoint.Text=cfg.base_url;model.Text=cfg.model;persona.SelectedIndex=Math.Max(0,Math.Min(2,cfg.personality));traits.Text=cfg.traits;
            var secret=Path.Combine(folder,"key.dpapi");
            if(File.Exists(secret)){key.Text=Encoding.UTF8.GetString(ProtectedData.Unprotect(File.ReadAllBytes(secret),null,DataProtectionScope.CurrentUser));remember.Checked=true;}
        }catch {Write("配置或本机密钥读取失败，请重新填写。");}
    }
    bool ValidateInput(out Uri uri){
        uri=null;
        if(!Uri.TryCreate(endpoint.Text.Trim().TrimEnd('/')+"/chat/completions",UriKind.Absolute,out uri) ||
           !(uri.Scheme=="https" || (uri.Scheme=="http" && uri.IsLoopback)) || !string.IsNullOrEmpty(uri.UserInfo) || !string.IsNullOrEmpty(uri.Query) || !string.IsNullOrEmpty(uri.Fragment)) {
            Write("地址需要使用 HTTPS；本机模型服务可使用 HTTP。请填写基础地址，不包含认证、查询参数或完整请求路径。");return false;
        }
        if(string.IsNullOrWhiteSpace(model.Text)){Write("请填写模型名称。");return false;}return true;
    }
    void Save(){
        Uri uri;if(!ValidateInput(out uri))return;
        try {
            Directory.CreateDirectory(folder);
            var cfg=new Settings{provider=provider.Text,base_url=endpoint.Text.Trim().TrimEnd('/'),model=model.Text.Trim(),personality=persona.SelectedIndex,traits=traits.Text};
            File.WriteAllText(Path.Combine(folder,"config.json"),json.Serialize(cfg),Encoding.UTF8);
            string path=Path.Combine(folder,"key.dpapi");
            if(remember.Checked && key.Text.Length>0)File.WriteAllBytes(path,ProtectedData.Protect(Encoding.UTF8.GetBytes(key.Text),null,DataProtectionScope.CurrentUser));
            else if(File.Exists(path))File.Delete(path);
            Write("配置已保存。"+(remember.Checked?"密钥由 Windows 按当前用户加密保存。":"密钥未持久保存。"));
        }catch {Write("保存失败，请检查本机配置目录是否可写。");}
    }
    async Task Test(){
        Uri uri;if(!ValidateInput(out uri))return;
        test.Enabled=false;
        int revision=configRevision;int selectedProvider=provider.SelectedIndex;
        bool passed=false;modelStatus.Text="● 模型链路：正在验证";modelStatus.ForeColor=muted;
        try {
            using(var handler=new HttpClientHandler{AllowAutoRedirect=false})
            using(var client=new HttpClient(handler)){
                client.Timeout=TimeSpan.FromSeconds(25);
                var request=new HttpRequestMessage(HttpMethod.Post,uri);
                if(!string.IsNullOrWhiteSpace(key.Text))request.Headers.Authorization=new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer",key.Text.Trim());
                var body=new System.Collections.Generic.Dictionary<string,object>();
                body["model"]=model.Text.Trim();body["messages"]=new[]{new{role="user",content="Connection test. Reply only OK."}};body["stream"]=false;
                body[selectedProvider==0?"max_completion_tokens":"max_tokens"]=128;
                request.Content=new StringContent(json.Serialize(body),Encoding.UTF8,"application/json");
                Write("正在测试连接……");
                using(var response=await client.SendAsync(request)){
                    if(!response.IsSuccessStatusCode){Write("连接未通过，HTTP "+(int)response.StatusCode+"。请检查地址、密钥、模型和服务商协议。");return;}
                    var text=await response.Content.ReadAsStringAsync();
                    var parsed=json.DeserializeObject(text) as System.Collections.Generic.Dictionary<string,object>;
                    var choices=parsed!=null && parsed.ContainsKey("choices")?parsed["choices"] as object[]:null;
                    if(choices==null || choices.Length==0){Write("服务返回成功，但响应不符合预期协议。");return;}
                    var first=choices[0] as System.Collections.Generic.Dictionary<string,object>;
                    var message=first!=null && first.ContainsKey("message")?first["message"] as System.Collections.Generic.Dictionary<string,object>:null;
                    if(message==null || !message.ContainsKey("content") || string.IsNullOrWhiteSpace(message["content"] as string)){Write("服务未返回有效文本，请检查模型及协议参数。");return;}
                    if(revision!=configRevision){Write("请求完成，但配置已变更，请重新验证。");return;}
                    passed=true;
                    modelStatus.Text="● 模型链路：连接通过";modelStatus.ForeColor=Color.FromArgb(157,192,122);
                    Write("模型连接测试通过。此结果仅验证端点协议，不代表游戏指挥功能已接通。");
                }
            }
        } catch(TaskCanceledException){Write("连接测试超时。");}
        catch {Write("请求失败，请检查网络、证书及端点协议。密钥与响应正文不会写入日志。");}
        finally{test.Enabled=true;if(!passed && revision==configRevision){modelStatus.Text="● 模型链路：验证未通过";modelStatus.ForeColor=Color.FromArgb(210,110,85);}}
    }
    public class Settings{public string provider{get;set;}public string base_url{get;set;}public string model{get;set;}public int personality{get;set;}public string traits{get;set;}}
    [STAThread]static void Main(string[] args){
        Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
        var form=new CommanderDesktop();
        if(args.Length==1 && args[0]=="--smoke"){var timer=new Timer{Interval=1000};timer.Tick+=(s,e)=>form.Close();timer.Start();}
        Application.Run(form);
    }
}
