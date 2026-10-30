# Starts a free Cloudflare quick tunnel to the Aegis Saathi server (http://localhost:8000).
# The public https://<random>.trycloudflare.com address is printed below; paste it into the
# Android app (menu -> Server settings). A NEW address is created every time this starts.
$exe = "C:\Users\Arkag\AppData\Local\Temp\claude\D--Deviathon\fc4b2167-0b66-4766-bb52-9c40086c4e75\scratchpad\cloudflared\cloudflared.exe"
if (-not (Test-Path $exe)) { $exe = "cloudflared" }
& $exe tunnel --url http://localhost:8000 --no-autoupdate
