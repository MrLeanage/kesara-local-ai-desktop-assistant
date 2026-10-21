using System;
using System.Collections.Concurrent;
using System.Speech.Synthesis;
using System.Text;
public class KesaraVoiceWorker {
  static readonly object outputLock=new object();
  static void Emit(string value) { lock(outputLock) { Console.WriteLine(value); Console.Out.Flush(); } }
  public static void Run() {
    Console.InputEncoding=Encoding.UTF8;
    using(var voice=new SpeechSynthesizer()) {
      var requests=new ConcurrentDictionary<Prompt,string>();
      voice.VisemeReached += (o,e) => { string id; if(requests.TryGetValue(e.Prompt,out id)) Emit("V|"+id+"|"+e.Viseme); };
      voice.SpeakCompleted += (o,e) => { string id; if(requests.TryRemove(e.Prompt,out id)) Emit("D|"+id+"|"+(e.Error==null?"ok":"error")); };
      Emit("R");
      string line;
      while((line=Console.ReadLine())!=null) {
        if(line=="Q") { voice.SpeakAsyncCancelAll(); break; }
        if(line=="X") { voice.SpeakAsyncCancelAll(); continue; }
        var parts=line.Split(new char[]{'|'},3);
        if(parts.Length==3 && parts[0]=="S") {
          try {
            var text=Encoding.UTF8.GetString(Convert.FromBase64String(parts[2]));
            var prompt=new Prompt(text); requests[prompt]=parts[1]; voice.SpeakAsync(prompt);
          } catch { Emit("D|"+parts[1]+"|error"); }
        }
      }
    }
  }
}
