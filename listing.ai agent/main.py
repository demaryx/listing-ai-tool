from agent import generate_product_copy

def main():
    print("\n🏷️  listing.ai — CLI Mode")
    print("─" * 40)
    product_name = input("Product name    : ").strip()
    features     = input("Key features    : ").strip()
    audience     = input("Target audience : ").strip()
    brand_name   = input("Brand name      : ").strip()
    platform     = input("Platform        : ").strip()

    print("\n⏳ Generating copy...\n")
    benefits, output = generate_product_copy(product_name, features, audience, brand_name, platform)

    print("── BENEFITS ──────────────────────────────")
    print(benefits)
    print("\n── COPY ──────────────────────────────────")
    print(output)
    print("─" * 40)

if __name__ == "__main__":
    main()