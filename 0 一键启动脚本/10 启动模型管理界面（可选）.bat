CHCP 65001
@echo off 
cd ../
echo 尝试启动程序，请耐心等待gradio启动，等待十几秒
start  http://127.0.0.1:9868
runtime\python.exe ./Inference/src/Character_Manager.py

pause