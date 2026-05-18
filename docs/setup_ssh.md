# Setup SSH

Complete SSH setup guide for the reMarkable 2-generating the RSA key, deploying it to the tablet, verifying the passwordless connection, and optional configuration of `~/.ssh/config`.

---
## Step 1 - Find the root password

On the tablet: **Menu -> Settings -> Help -> Copyrights and licenses**

At the very bottom of the screen:
```text
Username: root
Password: <password displayed>
```

> This password may change after a firmware update. If the SSH connection is denied after an update, return here to check it again and re-deploy the key (step 4).

---
## Step 2 - Connect the tablet via USB

Plug in the USB-C cable. The tablet exposes a static network interface at `10.11.99.1`.

Verify that the connection is active using PowerShell:
```bash
ping 10.11.99.1
```

---
## Step 3 - Generate the RSA SSH key

```powershell
# Windows PowerShell
ssh-keygen -t rsa -b 4096 -f $env:USERPROFILE\.ssh\id_rsa_remarkable
```

```bash
# Linux / macOS
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa_remarkable
```

Leave the passphrase **blank** (press Enter twice) - required for `paramiko` to connect without interaction.

This creates two files:
```
~/.ssh/id_rsa_remarkable      <- private key (never share)
~/.ssh/id_rsa_remarkable.pub  <- public key (to be placed on the tablet)
```

---
## Step 4 - Deploy the public key to the tablet

You will be prompted for the root password-this is the **only and last time**.

### Windows

```powershell
# 1. Create ~/.ssh on the tablet with the correct permissions
ssh root@10.11.99.1 “mkdir -p ~/.ssh && chmod 700 ~/.ssh"

# 2. Deploy the key and secure authorized_keys
type $env:USERPROFILE\.ssh\id_rsa_remarkable.pub | ssh root@10.11.99.1 “cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

### Linux / macOS

```bash
ssh-copy-id -i ~/.ssh/id_rsa_remarkable.pub root@10.11.99.1
```

> `chmod 700` on `~/.ssh/` and `chmod 600` on `authorized_keys` are required
> SSH refuses to read the file if the permissions are too permissive.

---
## Step 5 - Verify the passwordless connection

```powershell
# Windows
ssh -i $env:USERPROFILE\.ssh\id_rsa_remarkable root@10.11.99.1
```

```bash
# Linux / macOS
ssh -i ~/.ssh/id_rsa_remarkable root@10.11.99.1
```

---
## Step 6 - Configure `~/.ssh/config` (optional but recommended)

Create or edit `~/.ssh/config`:

```text
Host remarkable-usb
    HostName 10.11.99.1
    User root
    IdentityFile ~/.ssh/id_rsa_remarkable
    ConnectTimeout 5
```

> Now you can use `ssh remarkable-usb` directly from the terminal.
> This file is for manual use, as `paramiko` uses the key path defined in `config.yaml`.