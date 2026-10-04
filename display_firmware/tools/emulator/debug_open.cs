using System;using System.Collections.Generic;using System.Linq;using System.Reflection;using System.Threading;using System.Windows.Forms;
// Plugin of the live agent: presses "Debug" of the editor (opens the emulator, form "apprun"); returns when the emulator is up.
public class Plugin {
  public static string Run(object ctx){
    Form main=null; foreach(var f in (List<Form>)ctx) if(f.GetType().Name=="main") main=f;
    if(main==null) return "the editor has no main form yet";
    var item=main.GetType().GetField("buttonItem18",BindingFlags.Instance|BindingFlags.NonPublic|BindingFlags.Public).GetValue(main);   // the "Debug" button
    main.BeginInvoke(new Action(delegate{ var t=item.GetType(); (t.GetMethod("RaiseClick",new Type[0])??t.GetMethod("PerformClick",new Type[0])).Invoke(item,null); }));   // not Invoke: the emulator is modal
    for(int i=0;i<90;i++){ Thread.Sleep(1000); try{ foreach(Form x in new List<Form>(Application.OpenForms.Cast<Form>())) if(x.GetType().Name=="apprun"&&x.Visible) return "emulator is up"; }catch{} }
    return "the emulator did not open";
  }
}
