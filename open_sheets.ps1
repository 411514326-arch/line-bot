# open_sheets.ps1
$url = "https://sheets.new"
Start-Process $url

Start-Sleep -Seconds 2

# 嘗試喚醒瀏覽器視窗置頂
Add-Type @"
  using System;
  using System.Runtime.InteropServices;
  public class Win32 {
    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool SetForegroundWindow(IntPtr hWnd);
  }
"@

$processes = Get-Process chrome, msedge -ErrorAction SilentlyContinue | Sort-Object StartTime -Descending
if ($processes) {
    [Win32]::SetForegroundWindow($processes[0].MainWindowHandle) | Out-Null
}
