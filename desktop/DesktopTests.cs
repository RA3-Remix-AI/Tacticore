using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;
class DesktopTests {
    static object Field(object form,string name){return form.GetType().GetField(name,BindingFlags.NonPublic|BindingFlags.Instance).GetValue(form);}
    static void Require(bool ok,string message){if(!ok)throw new Exception(message);}
    static async Task Check(Form form){
        var provider=(ComboBox)Field(form,"provider");var key=(TextBox)Field(form,"key");var endpoint=(TextBox)Field(form,"endpoint");var model=(TextBox)Field(form,"model");var status=(Label)Field(form,"modelStatus");
        provider.SelectedIndex=0;key.Text="fake-test-key";provider.SelectedIndex=1;
        Require(key.Text=="","Provider switch must clear key");Require(endpoint.Text=="https://api.deepseek.com","DeepSeek preset");Require(model.Text=="deepseek-flash","DeepSeek model preset");
        provider.SelectedIndex=2;Require(!endpoint.ReadOnly,"Custom endpoint editable");
        var portPicker=new TcpListener(IPAddress.Loopback,0);portPicker.Start();int port=((IPEndPoint)portPicker.LocalEndpoint).Port;portPicker.Stop();
        using(var server=new HttpListener()){
            server.Prefixes.Add("http://127.0.0.1:"+port+"/");server.Start();
            endpoint.Text="http://127.0.0.1:"+port;model.Text="mock-model";key.Text="fake-test-key";
            string[] replies={"{\"choices\":[{\"message\":{\"content\":\"OK\"}}]}","{\"choices\":[]}"};
            for(int i=0;i<replies.Length;i++){
                string reply=replies[i];
                var serve=Task.Run(()=>{var request=server.GetContext();using(var reader=new StreamReader(request.Request.InputStream)){
                    string body=reader.ReadToEnd();Require(body.Contains("mock-model"),"Model request missing");Require(body.Contains("max_tokens"),"Custom token parameter missing");
                    Require(request.Request.Url.AbsolutePath=="/chat/completions","Wrong API path");Require(request.Request.Headers["Authorization"]=="Bearer fake-test-key","Wrong authentication");
                }byte[] bytes=Encoding.UTF8.GetBytes(reply);request.Response.ContentType="application/json";request.Response.ContentLength64=bytes.Length;request.Response.OutputStream.Write(bytes,0,bytes.Length);request.Response.Close();});
                await (Task)form.GetType().GetMethod("Test",BindingFlags.NonPublic|BindingFlags.Instance).Invoke(form,null);await serve;
                Require(i==0?status.Text.Contains("连接通过"):status.Text.Contains("未通过"),"Connection result state incorrect");
            }
        }
        Console.WriteLine("PASS: provider defaults, credential isolation, custom request/auth, valid response, invalid response clears success");
    }
    [STAThread]static int Main(){
        Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);int exit=0;
        Form form=(Form)Activator.CreateInstance(typeof(CommanderDesktop),true);form.Shown+=async(s,e)=>{try{await Check(form);}catch(Exception error){Console.Error.WriteLine(error.Message);exit=1;}finally{form.Close();}};
        form.ShowInTaskbar=false;form.Opacity=0;Application.Run(form);return exit;
    }
}
