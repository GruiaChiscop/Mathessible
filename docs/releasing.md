# Releasing

The Release workflow (`.github/workflows/release.yml`) builds the packaged
applications: a disk image for macOS (Apple silicon) and a zipped folder for
Windows (x64). Run by hand (Actions › Release › Run workflow), it only builds
them, as artifacts to try. Pushing a tag such as `v0.1.0` also publishes them
as a GitHub release, with that version's section of `CHANGELOG.md` as notes.

## Signing and notarising for macOS

Without the secrets below the disk image is built unsigned, and macOS refuses
to open the downloaded application until the user allows it in System
Settings › Privacy & Security. With them, the application and the disk image
are signed with a Developer ID, notarised by Apple and stapled, so they open
like any other application, even without a network connection.

This needs a paid Apple Developer Program membership.

### 1. A Developer ID Application certificate

Only the account holder can create one.

1. In Xcode, open Settings › Accounts, choose the team and click Manage
   Certificates.
2. Add (+) a **Developer ID Application** certificate. It is installed in the
   login keychain.
3. In Keychain Access, under My Certificates, find "Developer ID Application:
   *name* (*team*)", expand it to check that its private key is there, and
   export the certificate with its key (File › Export Items) as a `.p12` file
   with a password.

### 2. An App Store Connect API key for notarisation

1. At App Store Connect, open Users and Access › Integrations › App Store
   Connect API (Team Keys) and generate a key with the **Developer** role.
2. Download the `.p8` file (it can be downloaded only once) and note its
   Key ID and the Issuer ID shown above the list of keys.

### 3. The repository's secrets

The Release workflow cannot see your keychain or your files: it reads five
*secrets*, values stored encrypted in the GitHub repository. Nobody can read
a secret back, not even you; it can only be replaced. A secret is text, so the
two files (the `.p12` and the `.p8`) are stored as base64, a way of writing a
file as text, and the workflow turns them back into files.

The secrets' names must be exactly these, in capitals:

1. `MACOS_CERTIFICATE`: the `.p12` file from step 1, as base64.
2. `MACOS_CERTIFICATE_PASSWORD`: the password you gave the `.p12` when
   exporting it.
3. `APPLE_API_KEY`: the `.p8` file from step 2, as base64.
4. `APPLE_API_KEY_ID`: the key's Key ID from step 2, ten letters and digits.
5. `APPLE_API_ISSUER`: the Issuer ID from step 2, a long identifier with
   dashes.

#### With the GitHub CLI (recommended)

In Terminal, in the repository's folder, after `gh auth login` if you have
not signed in to `gh` yet. Each command sets one secret; replace the file
paths with where your files are.

The certificate, turned into base64 on the way (nothing is printed):

```sh
base64 -i ~/Downloads/certificate.p12 | gh secret set MACOS_CERTIFICATE
```

The certificate's password: the command asks for it, and does not show what
you type.

```sh
gh secret set MACOS_CERTIFICATE_PASSWORD
```

The API key file, turned into base64 the same way:

```sh
base64 -i ~/Downloads/AuthKey_ABCDE12345.p8 | gh secret set APPLE_API_KEY
```

The Key ID and the Issuer ID: each command asks for its value; paste it.

```sh
gh secret set APPLE_API_KEY_ID
```

```sh
gh secret set APPLE_API_ISSUER
```

Check that all five are there (only their names and dates are listed):

```sh
gh secret list
```

#### On the GitHub website

On the repository's page: the Settings tab, then Secrets and variables ›
Actions in the side bar, then the button New repository secret. Type the
secret's name in Name, paste its value in Secret, and press Add secret.
Repeat for each of the five. For the two files, copy their base64 to the
clipboard first, then paste it as the value:

```sh
base64 -i ~/Downloads/certificate.p12 | pbcopy
```

```sh
base64 -i ~/Downloads/AuthKey_ABCDE12345.p8 | pbcopy
```

#### Afterwards

Delete the exported `.p12` (the certificate stays in your keychain). Keep the
`.p8` somewhere safe outside the repository: Apple does not let you download
it again, and without it a new key has to be made. To check the setup, run
the Release workflow by hand: its "Disk image on macOS" step ends with
`accepted`, `source=Notarized Developer ID` instead of "Not signed".

### Signing a local build

With the certificate in the login keychain:

```sh
MATHESSIBLE_CODESIGN_IDENTITY="Developer ID Application" \
    uv run --group packaging pyinstaller packaging/mathessible.spec --noconfirm
MATHESSIBLE_CODESIGN_IDENTITY="Developer ID Application" \
    APPLE_API_KEY_PATH=/path/to/AuthKey_XXXX.p8 APPLE_API_KEY_ID=... APPLE_API_ISSUER=... \
    scripts/make-dmg.sh Mathessible-macOS-arm64.dmg
```

Without the variables, the same two commands build an unsigned disk image.
