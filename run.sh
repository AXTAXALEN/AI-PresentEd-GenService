#!/bin/bash
# Активируем виртуальное окружение
source /home/adminstudent/projects/gen-service/venv/bin/activate

# Прописываем пути к библиотекам NVIDIA
export LLAMA_CUDA=on
export CUDA_VISIBLE_DEVICES=0
export LD_LIBRARY_PATH=/lib/x86_64-linux-gnu:/usr/lib64-nvidia:$LD_LIBRARY_PATH

# Запускаем микросервис
exec python3 -u /home/adminstudent/projects/gen-service/main.py
