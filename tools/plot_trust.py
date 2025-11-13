from monitor.plot_utils import plot_timeline

if __name__ == "__main__":
    path = plot_timeline("agent-user-01")
    print(f"✅ Trust timeline saved to {path}")
