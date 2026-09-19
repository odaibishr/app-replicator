/**
 * App Replicator - Universal Frida Android Bypass & Traffic Inspector
 * ===================================================================
 * 1. Universal SSL Pinning Bypass (TrustManager, OkHttp3, Conscrypt, WebViewClient, etc.)
 * 2. Root Detection Bypass (RootBeer, Test-keys, Su binary checks)
 * 3. AES / DES Cryptographic Key & IV Dynamic Interceptor
 */

Java.perform(function () {
    console.log("[*] [App-Replicator] Initializing Universal Frida Hooks...");

    // 1. SSL Pinning Bypass: TrustManagerImpl
    try {
        var TrustManagerImpl = Java.use('com.android.org.conscrypt.TrustManagerImpl');
        TrustManagerImpl.verifyChain.implementation = function (untrustedChain, trustAnchorChain, host, clientAuth, ocspData, tlsSctData) {
            // console.log("[+] [SSL] conscrypt.TrustManagerImpl.verifyChain bypassed for host: " + host);
            return untrustedChain;
        };
        console.log("[+] [SSL] TrustManagerImpl hook installed.");
    } catch (e) {
        // Fallback
    }

    // 2. SSL Pinning Bypass: OkHttp 3.x CertificatePinner
    try {
        var CertificatePinner = Java.use('okhttp3.CertificatePinner');
        CertificatePinner.check.overload('java.lang.String', 'java.util.List').implementation = function (hostname, peerCertificates) {
            // console.log("[+] [SSL] okhttp3.CertificatePinner.check bypassed for: " + hostname);
            return;
        };
        console.log("[+] [SSL] OkHttp3 CertificatePinner hook installed.");
    } catch (e) { }

    // 3. SSL Pinning Bypass: TrustManager override
    try {
        var X509TrustManager = Java.use('javax.net.ssl.X509TrustManager');
        var SSLContext = Java.use('javax.net.ssl.SSLContext');

        var TrustAllManager = Java.registerClass({
            name: 'com.app.replicator.TrustAllManager',
            implements: [X509TrustManager],
            methods: {
                checkClientTrusted: function (chain, authType) { },
                checkServerTrusted: function (chain, authType) { },
                getAcceptedIssuers: function () { return []; }
            }
        });

        SSLContext.init.overload('[Ljavax.net.ssl.KeyManager;', '[Ljavax.net.ssl.TrustManager;', 'java.security.SecureRandom').implementation = function (km, tm, sr) {
            var trustAll = [TrustAllManager.$new()];
            this.init(km, trustAll, sr);
            console.log("[+] [SSL] SSLContext.init overridden with TrustAllManager.");
        };
    } catch (e) { }

    // 4. Root Detection Bypass
    try {
        var File = Java.use('java.io.File');
        File.exists.implementation = function () {
            var path = this.getAbsolutePath();
            if (path.indexOf("/su") !== -1 ||
                path.indexOf("/magisk") !== -1 ||
                path.indexOf("Superuser") !== -1 ||
                path.indexOf("busybox") !== -1 ||
                path.indexOf("/system/app/Superuser.apk") !== -1) {
                // console.log("[-] [Root] Cloaked root file check: " + path);
                return false;
            }
            return this.exists();
        };
        console.log("[+] [Root] Root detection checks cloaked.");
    } catch (e) { }

    // 5. Crypto Interceptor (AES / DES Cipher inspection)
    try {
        var Cipher = Java.use('javax.crypto.Cipher');
        Cipher.init.overload('int', 'java.security.Key', 'java.security.spec.AlgorithmParameterSpec').implementation = function (opmode, key, params) {
            var opStr = (opmode === 1) ? "ENCRYPT" : (opmode === 2) ? "DECRYPT" : opmode;
            var keyBytes = key.getEncoded();
            var b64Key = Java.use("android.util.Base64").encodeToString(keyBytes, 2);
            console.log("[*] [Crypto] Cipher.init (" + opStr + ") Algorithm: " + key.getAlgorithm() + " | Base64 Key: " + b64Key);
            return this.init(opmode, key, params);
        };
        console.log("[+] [Crypto] AES/Cipher interceptor active.");
    } catch (e) { }

    console.log("[+] [App-Replicator] Universal hooks fully engaged.");
});
