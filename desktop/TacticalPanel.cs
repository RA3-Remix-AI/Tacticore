using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Windows.Forms;

class TacticalPanel : Panel {
    public bool Header;public int Personality;public string CommanderName;
    public TacticalPanel(){DoubleBuffered=true;ResizeRedraw=true;}
    protected override void OnPaint(PaintEventArgs e){
        base.OnPaint(e);var g=e.Graphics;g.SmoothingMode=SmoothingMode.AntiAlias;
        Color gold=Color.FromArgb(205,169,94),ink=Color.FromArgb(229,220,192);
        using(var brush=new SolidBrush(Color.FromArgb(22,25,23)))g.FillRectangle(brush,ClientRectangle);
        using(var pen=new Pen(Color.FromArgb(73,69,52)))g.DrawRectangle(pen,0,0,Width-1,Height-1);
        using(var brush=new SolidBrush(Color.FromArgb(156,34,30)))g.FillRectangle(brush,0,0,Header?8:Width,Header?Height:5);
        using(var pen=new Pen(Color.FromArgb(35,39,34)))for(int x=-Height;x<Width;x+=24)g.DrawLine(pen,x,Height,x+Height,0);
        if(Header){
            Draw(g,"三极战线",24,14,23,ink,true);Draw(g,"战术指挥终端  /  AI COMMAND",25,56,10,gold,false);
            Draw(g,"COMMAND NETWORK",Width-245,24,12,gold,true);Draw(g,"战略判断  →  本地执行",Width-245,49,10,ink,false);
            return;
        }
        Draw(g,"指挥官档案",20,23,12,gold,true);
        float cx=Width/2f,cy=143,r=65;
        using(var pen=new Pen(gold,2)){g.DrawEllipse(pen,cx-r,cy-r,r*2,r*2);g.DrawEllipse(pen,cx-r+8,cy-r+8,(r-8)*2,(r-8)*2);}
        PointF[] points=new PointF[10];for(int i=0;i<10;i++){double angle=-Math.PI/2+i*Math.PI/5;float radius=i%2==0?44:20;points[i]=new PointF(cx+(float)Math.Cos(angle)*radius,cy+(float)Math.Sin(angle)*radius);}
        using(var brush=new SolidBrush(Color.FromArgb(184,46,36)))g.FillPolygon(brush,points);
        string[] names={"突击指挥官","经营指挥官","游击指挥官"};string[] desc={"集中突破 · 抢占先机","稳固后方 · 厚积薄发","多线牵制 · 袭扰经济"};
        Draw(g,string.IsNullOrWhiteSpace(CommanderName)?names[Personality]:CommanderName,20,229,17,ink,true);Draw(g,desc[Personality],20,266,10,gold,false);
        string[] labels={"攻势倾向","经济倾向","机动倾向"};int[,] scores={{9,5,5},{4,9,4},{6,5,9}};
        for(int i=0;i<3;i++){
            Draw(g,labels[i],20,324+i*52,10,ink,false);
            for(int b=0;b<10;b++)using(var brush=new SolidBrush(b<scores[Personality,i]?gold:Color.FromArgb(48,49,40)))g.FillRectangle(brush,20+b*20,349+i*52,15,5);
        }
        using(var pen=new Pen(Color.FromArgb(73,69,52)))g.DrawLine(pen,20,503,Width-20,503);
        Draw(g,"联动状态 / 见实时战局",20,524,11,gold,true);
        Draw(g,"遭遇战选择指挥官\n模型制定战略\n本地 AI 执行与微操",20,556,10,ink,false);
        if(Height>735)Draw(g,"按当前会话核验绑定\n保留原生 AI 接续",20,Height-65,9,Color.FromArgb(156,151,131),false);
    }
    void Draw(Graphics g,string text,float x,float y,float size,Color color,bool bold){using(var font=new Font("Microsoft YaHei UI",size,bold?FontStyle.Bold:FontStyle.Regular))using(var brush=new SolidBrush(color))g.DrawString(text,font,brush,x,y);}
}
