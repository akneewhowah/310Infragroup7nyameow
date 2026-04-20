@ECHO OFF
"C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\MSBuild\Current\Bin\MSBuild.exe" Client.sln /t:Clean,Build /p:Configuration=Release /p:Platform=x64 /p:RuntimeLibrary=MultiThreaded
copy x64\Release\Client.exe .