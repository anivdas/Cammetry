# Encrypted Tesla dashcam recordings

Newer Tesla software can save Dashcam recordings in an `EncryptedClips` folder when **Encrypt Dashcam Recordings** is enabled.

Cammetry intentionally does **not** request, store, or proxy Tesla account credentials or vehicle decryption keys. Encrypted recordings are left untouched and are not treated as playable clips.

## How to use encrypted recordings with Cammetry

1. Connect the Tesla USB drive to the computer.
2. Open Tesla's official Dashcam web viewer: <https://dashcam.tesla.com>
3. Sign in with a Tesla account that was linked to the vehicle when the recordings were created.
4. Follow Tesla's instructions to decrypt the recordings locally in the browser.
5. Save/use the decrypted recordings and scan that location with Cammetry.

Tesla's owner documentation states that encrypted recordings cannot be played directly on a computer and that the official browser viewer retrieves the required decryption keys and decrypts the files locally. Dashcam clips themselves are not uploaded to Tesla as part of that browser decryption flow.

Official Tesla documentation:

- <https://www.tesla.com/ownersmanual/cybertruck/en_us/GUID-F311BBCA-2532-4D04-B88C-DBA784ADEE21.html>

## Why Cammetry does not decrypt them directly

A native Cammetry decryptor would need a supported way to authenticate the owner and retrieve the vehicle-specific decryption material. Cammetry will not reverse-engineer Tesla account authentication, capture browser tokens, ask users to paste account passwords, or embed unofficial credential-handling code.

If Tesla publishes a supported API or desktop integration for this workflow in the future, Cammetry can evaluate adding a local-only integration while preserving its no-background-login and privacy-first design.
