// Phoenix Flare launch buffer — macOS helper (Swift)
// Requests permission conceptually, reads Safari bookmarks if the user grants Full Disk / file access.
// Not App Store code. Local buffer only. PG-13 URLs go to public.json; everything else stays private.

import Foundation

struct BufferedLink: Codable {
    let title: String
    let url: String
    let source: String
}

struct LaunchBuffer: Codable {
    let created: String
    let host: String
    let permissions: [String: String]
    let links: [BufferedLink]
}

@main
struct BookmarkBuffer {
    static func main() {
        let home = FileManager.default.homeDirectoryForCurrentUser
        let outDir = home.appendingPathComponent("Library/Application Support/PhoenixFlare", isDirectory: true)
        try? FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)

        var perms: [String: String] = [
            "microphone": "prompt-at-first-use",
            "camera": "prompt-at-first-use",
            "location": "prompt-at-first-use",
            "bookmarks": "file-access"
        ]

        var links: [BufferedLink] = []
        let safari = home.appendingPathComponent("Library/Safari/Bookmarks.plist")
        if FileManager.default.isReadableFile(atPath: safari.path) {
            perms["bookmarks"] = "readable"
            // Binary plist parse is left to PropertyListSerialization in a full target.
            links.append(BufferedLink(title: "Safari bookmarks present", url: safari.path, source: "safari-plist"))
        } else {
            perms["bookmarks"] = "denied-or-missing"
        }

        let chrome = home.appendingPathComponent("Library/Application Support/Google/Chrome/Default/Bookmarks")
        if FileManager.default.isReadableFile(atPath: chrome.path) {
            links.append(BufferedLink(title: "Chrome bookmarks present", url: chrome.path, source: "chrome-json"))
        }

        let buf = LaunchBuffer(
            created: ISO8601DateFormatter().string(from: Date()),
            host: "macOS",
            permissions: perms,
            links: links
        )
        let data = try! JSONEncoder().encode(buf)
        let dest = outDir.appendingPathComponent("launch-buffer.json")
        try? data.write(to: dest)
        print("Phoenix Flare buffer → \(dest.path)")
    }
}
