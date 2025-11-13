from Crypto.PublicKey import RSA

def main():
    key = RSA.generate(2048)
    private_key = key.export_key()
    public_key = key.publickey().export_key()

    with open("tools/private.pem", "wb") as f:
        f.write(private_key)
    with open("tools/public.pem", "wb") as f:
        f.write(public_key)

    print("✅ RSA keypair generated under ./tools/")

if __name__ == "__main__":
    main()
