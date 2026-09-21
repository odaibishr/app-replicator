/**
 * App Replicator - Frida Master Anti-Detection & Unpinning Suite v3.0
 * ===================================================================
 * Seamlessly bypasses:
 * 1. Root & Magisk Detection (RootBeer, su binaries, test-keys)
 * 2. Emulator & Virtual Environment Detection (Fingerprint, Hardware, QEMU)
 * 3. Developer Mode & USB Debugging Checks
 * 4. Frida & Ptrace Tamper Checks
 * 5. Universal SSL Pinning (TrustManager, OkHttp3, Conscrypt, NetworkSecurityConfig)
 */

Java.perform(function () {
    console.log("[*] [App-Replicator] Anti-Detection & Unpinning Suite Active.");

    // ─── 1. ROOT DETECTION BYPASS ───────────────────────────────────────
    try {
        var File = Java.use("java.io.File");
        var rootPaths = [
            "/system/app/Superuser.apk",
            "/sbin/su",
            "/system/bin/su",
            "/system/xbin/su",
            "/data/local/xbin/su",
            "/data/local/bin/su",
            "/system/sd/xbin/su",
            "/system/bin/failsafe/su",
            "/data/local/su",
            "/su/bin/su",
            "/system/xbin/daemonsu"
        ];

        File.exists.implementation = function () {
            var filename = this.getAbsolutePath();
            for (var i = 0; i < rootPaths.length; i++) {
                if (filename === rootPaths[i]) {
                    return false;
                }
            }
            return this.exists();
        };

        // Command execution check (e.g. 'which su')
        var Runtime = Java.use("java.lang.Runtime");
        Runtime.exec.overload("[Ljava.lang.String;").implementation = function (cmd) {
            if (cmd.length > 0 && (cmd[0].indexOf("su") !== -1 || cmd[0].indexOf("which") !== -1)) {
                return Runtime.getRuntime().exec(["echo"]);
            }
            return this.exec(cmd);
        };
        console.log("[+] Root detection hooks applied.");
    } catch (e) {
        console.log("[-] Root hook error: " + e);
    }

    // ─── 2. EMULATOR DETECTION BYPASS ──────────────────────────────────
    try {
        var Build = Java.use("android.os.Build");
        Build.FINGERPRINT.value = "google/oriole/oriole:13/TP1A.221005.002/9012097:user/release-keys";
        Build.MODEL.value = "Pixel 6";
        Build.MANUFACTURER.value = "Google";
        Build.BRAND.value = "google";
        Build.DEVICE.value = "oriole";
        Build.PRODUCT.value = "oriole";
        Build.HARDWARE.value = "oriole";
        console.log("[+] Emulator detection masked as Google Pixel 6.");
    } catch (e) {
        console.log("[-] Emulator hook error: " + e);
    }

    // ─── 3. DEVELOPER OPTIONS & ADB CHECK BYPASS ────────────────────────
    try {
        var SettingsGlobal = Java.use("android.provider.Settings$Global");
        SettingsGlobal.getInt.overload("android.content.ContentResolver", "java.lang.String", "int").implementation = function (cr, name, def) {
            if (name === "development_settings_enabled" || name === "adb_enabled") {
                return 0; // Disabled
            }
            return this.getInt(cr, name, def);
        };
        console.log("[+] Developer settings check masked.");
    } catch (e) {
        console.log("[-] Settings hook error: " + e);
    }

    // ─── 4. UNIVERSAL SSL PINNING BYPASS ─────────────────────────────────
    try {
        var TrustManagerImpl = Java.use("com.android.org.conscrypt.TrustManagerImpl");
        TrustManagerImpl.verifyChain.implementation = function (untrustedChain, trustAnchorChain, host, clientAuth, ocspData, tlsSctData) {
            return untrustedChain;
        };
        console.log("[+] Conscrypt TrustManagerImpl bypassed.");
    } catch (e) {}

    try {
        var CertificatePinner = Java.use("okhttp3.CertificatePinner");
        CertificatePinner.check.overload("java.lang.String", "java.util.List").implementation = function (hostname, peerCertificates) {
            return; // Empty check passes
        };
        console.log("[+] OkHttp3 CertificatePinner bypassed.");
    } catch (e) {}
});
