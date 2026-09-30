// Phoenix Flare launch buffer — iOS helper (Swift)
// Safari bookmarks are not readable by third-party apps.
// This helper: (1) request mic / camera / location at launch,
// (2) accept a user-picked bookmarks.html via document picker,
// (3) write a local JSON buffer the listen webview can load.

import Foundation

#if canImport(AVFoundation)
import AVFoundation
#endif
#if canImport(CoreLocation)
import CoreLocation
#endif

public struct BufferedLink: Codable {
    public let title: String
    public let url: String
    public let source: String
}

public struct LaunchBuffer: Codable {
    public let created: String
    public let host: String
    public let permissions: [String: String]
    public let links: [BufferedLink]
}

public final class PhoenixLaunchBuffer: NSObject {
    public static let shared = PhoenixLaunchBuffer()
    private let fm = FileManager.default

    public var bufferURL: URL {
        let dir = fm.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("PhoenixFlare", isDirectory: true)
        try? fm.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appendingPathComponent("launch-buffer.json")
    }

    public func requestDevicePermissions(completion: @escaping ([String: String]) -> Void) {
        var result: [String: String] = [:]
        #if canImport(AVFoundation)
        AVCaptureDevice.requestAccess(for: .audio) { mic in
            result["microphone"] = mic ? "granted" : "denied"
            AVCaptureDevice.requestAccess(for: .video) { cam in
                result["camera"] = cam ? "granted" : "denied"
                result["location"] = "prompt-in-CLLocationManager"
                result["bookmarks"] = "document-picker-only"
                completion(result)
            }
        }
        #else
        result["note"] = "compile inside an iOS target"
        completion(result)
        #endif
    }

    public func ingestBookmarksHTML(_ html: String, permissions: [String: String]) throws {
        let re = try NSRegularExpression(pattern: "href=[\"'](https?://[^\"']+)[\"'][^>]*>([^<]*)", options: [.caseInsensitive])
        let range = NSRange(html.startIndex..<html.endIndex, in: html)
        var links: [BufferedLink] = []
        re.enumerateMatches(in: html, options: [], range: range) { match, _, _ in
            guard let match, match.numberOfRanges >= 3,
                  let r1 = Range(match.range(at: 1), in: html),
                  let r2 = Range(match.range(at: 2), in: html) else { return }
            links.append(BufferedLink(title: String(html[r2]), url: String(html[r1]), source: "bookmarks.html"))
        }
        let buf = LaunchBuffer(
            created: ISO8601DateFormatter().string(from: Date()),
            host: "iOS",
            permissions: permissions,
            links: links
        )
        let data = try JSONEncoder().encode(buf)
        try data.write(to: bufferURL, options: .atomic)
    }
}
