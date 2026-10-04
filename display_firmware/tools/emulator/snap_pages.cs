using System;using System.Collections.Generic;using System.Drawing;using System.Drawing.Imaging;using System.IO;using System.Reflection;using System.Text;using System.Threading;using System.Windows.Forms;
// Plugin of the live agent of the USART HMI editor (QSART_Linux_EN, see tools/emulator/README.md).
// For every page named in pages.txt: types "page NAME" into the command box of the emulator, presses "run all code" and saves the screen control as PNG.
public class Plugin {
  static Control Find(Control c,string name){ if(c.Name==name)return c; foreach(Control x in c.Controls){ var r=Find(x,name); if(r!=null)return r; } return null; }
  public static string Run(object ctx){
    var sb=new StringBuilder(); Form emu=null; foreach(var f in (List<Form>)ctx) if(f.GetType().Name=="apprun") emu=f;
    string dir=Environment.GetEnvironmentVariable("AGENT_DIR"); string outDir=File.ReadAllText(Path.Combine(dir,"outdir.txt")).Trim();
    Directory.CreateDirectory(outDir);
    var editor=Find(emu,"textEditorControl1"); var run=Find(emu,"button1"); var scr=Find(emu,"runscr1");
    if(editor==null||run==null||scr==null) return "controls not found "+(editor!=null)+(run!=null)+(scr!=null);
    var textProp=editor.GetType().GetProperty("Text");
    int ok=0;
    foreach(var line in File.ReadAllLines(Path.Combine(dir,"pages.txt"))){
      string name=line.Trim(); if(name.Length==0)continue;
      emu.Invoke(new Action(delegate{ textProp.SetValue(editor,"page "+name,null); emu.GetType().GetMethod("sendall",BindingFlags.Instance|BindingFlags.NonPublic|BindingFlags.Public).Invoke(emu,null); }));
      Thread.Sleep(900);
      try{
        emu.Invoke(new Action(delegate{
          using(var bmp=new Bitmap(scr.Width,scr.Height)){ scr.DrawToBitmap(bmp,new Rectangle(0,0,scr.Width,scr.Height)); bmp.Save(Path.Combine(outDir,name+".png"),ImageFormat.Png); }
        }));
        ok++;
      }catch(Exception e){ sb.AppendLine(name+": "+e.Message); }
    }
    sb.AppendLine("saved "+ok); return sb.ToString(); }
}
