import Cocoa
import WebKit

class RemuxVaultAppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate {
    var window: NSWindow!
    var webView: WKWebView!

    func applicationDidFinishLaunching(_ notification: Notification) {
        let rect = NSRect(x: 0, y: 0, width: 1260, height: 840)
        window = NSWindow(
            contentRect: rect,
            styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
            backing: .buffered,
            defer: false
        )
        window.title = "Remux Vault"
        window.titlebarAppearsTransparent = true
        window.titleVisibility = .hidden
        window.backgroundColor = NSColor(calibratedRed: 8.0/255.0, green: 13.0/255.0, blue: 26.0/255.0, alpha: 1.0)
        window.center()
        window.setFrameAutosaveName("RemuxVaultMainWindowFrame")

        let config = WKWebViewConfiguration()
        config.preferences.setValue(true, forKey: "developerExtrasEnabled")
        
        let prefs = WKWebpagePreferences()
        prefs.allowsContentJavaScript = true
        config.defaultWebpagePreferences = prefs

        webView = WKWebView(frame: window.contentView!.bounds, configuration: config)
        webView.autoresizingMask = [.width, .height]
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.setValue(false, forKey: "drawsBackground") // Prevents white flash on load

        window.contentView?.addSubview(webView)
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)

        loadDashboard()
    }

    func loadDashboard() {
        let tokenFile = "/Users/scottsnow/.gemini/antigravity/scratch/my-pi-project/.app_token"
        let token = (try? String(contentsOfFile: tokenFile, encoding: .utf8).trimmingCharacters(in: .whitespacesAndNewlines)) ?? ""
        let targetUrl = token.isEmpty ? "http://127.0.0.1:58239/" : "http://127.0.0.1:58239/?token=\(token)"
        if let url = URL(string: targetUrl) {
            var req = URLRequest(url: url)
            req.timeoutInterval = 10.0
            webView.load(req)
        }
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag {
            window?.makeKeyAndOrderFront(nil)
        }
        NSApp.activate(ignoringOtherApps: true)
        return true
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return false // Keeps app running in Dock ready for instant recall
    }

    // Intercept link clicks: internal library navigation stays inside the app;
    // external links (IMDb, Letterboxd, Sheets, download links) open in the user's default browser
    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url else {
            decisionHandler(.cancel)
            return
        }

        let host = url.host?.lowercased() ?? ""
        if host == "127.0.0.1" || host == "localhost" || url.scheme == "data" || url.scheme == "about" {
            decisionHandler(.allow)
        } else {
            NSWorkspace.shared.open(url)
            decisionHandler(.cancel)
        }
    }

    // Handle target="_blank" window creation by routing external links out to default browser
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = navigationAction.request.url {
            let host = url.host?.lowercased() ?? ""
            if host == "127.0.0.1" || host == "localhost" {
                webView.load(navigationAction.request)
            } else {
                NSWorkspace.shared.open(url)
            }
        }
        return nil
    }

    // Gracefully handle connection retry if daemon was starting
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) { [weak self] in
            self?.loadDashboard()
        }
    }
}

let app = NSApplication.shared
let delegate = RemuxVaultAppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
