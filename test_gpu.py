import torch

print("=" * 50)
print("PyTorch GPU 检测")
print("=" * 50)
print(f"PyTorch 版本: {torch.__version__}")
print(f"CUDA 可用: {torch.cuda.is_available()}")
print(f"GPU 数量: {torch.cuda.device_count()}")

if torch.cuda.is_available():
    print(f"\n✓ GPU 检测成功!")
    for i in range(torch.cuda.device_count()):
        print(f"  GPU {i}: {torch.cuda.get_device_name(i)}")
        print(f"       显存: {torch.cuda.get_device_properties(i).total_memory / 1e9:.1f} GB")
else:
    print("\n✗ 未检测到 GPU，使用 CPU")

print("=" * 50)
