using System;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Windows.Forms;

class DarkComboBox : ComboBox {
    [DllImport("user32.dll")]static extern IntPtr GetWindowDC(IntPtr hwnd);
    [DllImport("user32.dll")]static extern int ReleaseDC(IntPtr hwnd,IntPtr dc);
    public DarkComboBox(){DropDownStyle=ComboBoxStyle.DropDownList;DrawMode=DrawMode.OwnerDrawFixed;FlatStyle=FlatStyle.Flat;BackColor=Color.FromArgb(17,21,19);ForeColor=Color.FromArgb(226,218,191);ItemHeight=24;IntegralHeight=true;}
    protected override void OnDrawItem(DrawItemEventArgs e){
        bool selected=(e.State&DrawItemState.Selected)!=0;
        using(var brush=new SolidBrush(selected?Color.FromArgb(113,34,29):BackColor))e.Graphics.FillRectangle(brush,e.Bounds);
        if(e.Index>=0)TextRenderer.DrawText(e.Graphics,GetItemText(Items[e.Index]),Font,new Rectangle(e.Bounds.X+7,e.Bounds.Y,e.Bounds.Width-10,e.Bounds.Height),ForeColor,TextFormatFlags.VerticalCenter|TextFormatFlags.EndEllipsis|TextFormatFlags.SingleLine);
    }
    protected override void WndProc(ref Message m){
        base.WndProc(ref m);
        if(m.Msg==0xF || m.Msg==0x85 || m.Msg==0x14){IntPtr dc=GetWindowDC(Handle);if(dc==IntPtr.Zero)return;try{using(var g=Graphics.FromHdc(dc)){
            if(!Enabled){using(var b=new SolidBrush(BackColor))g.FillRectangle(b,2,2,Width-27,Height-4);if(SelectedIndex>=0)TextRenderer.DrawText(g,GetItemText(SelectedItem),Font,new Rectangle(7,2,Width-35,Height-4),Color.FromArgb(162,159,141),TextFormatFlags.VerticalCenter|TextFormatFlags.EndEllipsis|TextFormatFlags.SingleLine);}
            var arrow=new Rectangle(Width-25,1,24,Height-2);using(var b=new SolidBrush(Color.FromArgb(42,42,34)))g.FillRectangle(b,arrow);
            using(var b=new SolidBrush(Color.FromArgb(205,169,94)))g.FillPolygon(b,new[]{new Point(Width-17,Height/2-2),new Point(Width-7,Height/2-2),new Point(Width-12,Height/2+3)});
            using(var pen=new Pen(Color.FromArgb(84,79,60),2))g.DrawRectangle(pen,1,1,Width-3,Height-3);
        }}finally{ReleaseDC(Handle,dc);}}
    }
}
class DarkButton : Button {
    public bool Primary;bool hover;
    public DarkButton(){FlatStyle=FlatStyle.Flat;UseVisualStyleBackColor=false;SetStyle(ControlStyles.UserPaint|ControlStyles.AllPaintingInWmPaint|ControlStyles.OptimizedDoubleBuffer,true);}
    protected override void OnMouseEnter(EventArgs e){base.OnMouseEnter(e);hover=true;Invalidate();}
    protected override void OnMouseLeave(EventArgs e){base.OnMouseLeave(e);hover=false;Invalidate();}
    protected override void OnEnabledChanged(EventArgs e){base.OnEnabledChanged(e);Invalidate();}
    protected override void OnPaint(PaintEventArgs e){
        Color background=!Enabled?Color.FromArgb(27,30,27):hover?Color.FromArgb(100,34,28):Primary?Color.FromArgb(163,37,31):Color.FromArgb(28,30,29);
        e.Graphics.Clear(background);using(var pen=new Pen(!Enabled?Color.FromArgb(68,68,54):Primary?Color.FromArgb(210,76,49):Color.FromArgb(83,79,61)))e.Graphics.DrawRectangle(pen,0,0,Width-1,Height-1);
        TextRenderer.DrawText(e.Graphics,Text,Font,new Rectangle(5,2,Width-10,Height-4),Enabled?Color.FromArgb(226,218,191):Color.FromArgb(163,160,143),TextFormatFlags.HorizontalCenter|TextFormatFlags.VerticalCenter|TextFormatFlags.SingleLine|TextFormatFlags.EndEllipsis);
        if(Focused&&Enabled)using(var pen=new Pen(Color.FromArgb(205,169,94)))e.Graphics.DrawRectangle(pen,3,3,Width-7,Height-7);
    }
}
class DarkTabControl : Panel {
    readonly FlowLayoutPanel strip=new FlowLayoutPanel();readonly Panel body=new Panel();
    readonly System.Collections.Generic.List<Control> pages=new System.Collections.Generic.List<Control>();
    readonly System.Collections.Generic.List<Button> buttons=new System.Collections.Generic.List<Button>();
    public DarkTabControl(){
        DoubleBuffered=true;BackColor=Color.FromArgb(14,16,15);
        strip.Dock=DockStyle.Top;strip.Height=40;strip.BackColor=BackColor;strip.Margin=Padding.Empty;strip.Padding=Padding.Empty;strip.WrapContents=false;
        body.Dock=DockStyle.Fill;body.BackColor=Color.FromArgb(72,68,51);body.Padding=new Padding(1);
        Controls.Add(body);Controls.Add(strip);
    }
    public void AddTab(string title,Control page){
        int index=pages.Count;var button=new Button{Text=title,AccessibleName=title,FlatStyle=FlatStyle.Flat,Width=165,Height=35,Margin=new Padding(0,0,5,5),ForeColor=Color.FromArgb(226,218,191),BackColor=Color.FromArgb(31,35,31),Cursor=Cursors.Hand};
        button.FlatAppearance.BorderColor=Color.FromArgb(82,77,58);button.FlatAppearance.MouseOverBackColor=Color.FromArgb(95,36,29);button.Click+=(s,e)=>Select(index);
        page.Dock=DockStyle.Fill;page.Margin=Padding.Empty;pages.Add(page);buttons.Add(button);body.Controls.Add(page);strip.Controls.Add(button);Select(0);
    }
    void Select(int index){for(int n=0;n<pages.Count;n++){pages[n].Visible=n==index;buttons[n].BackColor=n==index?Color.FromArgb(128,34,29):Color.FromArgb(31,35,31);buttons[n].FlatAppearance.BorderColor=n==index?Color.FromArgb(189,81,49):Color.FromArgb(82,77,58);}pages[index].BringToFront();}
}
