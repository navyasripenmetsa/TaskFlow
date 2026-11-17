# TaskFlow native messaging host

The native host reports desktop device information to the Chrome extension.
Its manifest and registry entry are generated for the current Windows account,
because Chrome requires an absolute executable path and an extension-specific
origin.

1. Install PyInstaller in the project environment.
2. From the project root, build the host:

   ```powershell
   pyinstaller --clean --noconfirm taskflow_native_host.spec
   ```

3. Load `chrome_extension/` as an unpacked extension and copy its ID from
   `chrome://extensions`.
4. Register the host from the project root:

   ```powershell
   .\native_host\install_taskflow_host.ps1 -ExtensionId <32-character-extension-id>
   ```

The installer validates the extension ID, writes the local
`native_host/com.taskflow.native.json` manifest, and registers it under the
current user's Chrome native-messaging registry key. The generated manifest is
ignored by Git because its path and extension ID are machine-specific.
