import sys
from agents.marketing import MarketingAgent

AGENTS = {
    "marketing": MarketingAgent,
}

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in AGENTS:
        print(f"\nBrug: python main.py [agent]")
        print(f"Tilgængelige agenter: {', '.join(AGENTS.keys())}")
        print(f"\nEksempel: python main.py marketing\n")
        sys.exit(1)

    agent_name = sys.argv[1]
    agent = AGENTS[agent_name]()
    agent.run()


if __name__ == "__main__":
    main()
