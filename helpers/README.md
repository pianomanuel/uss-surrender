# Phoenix Flare helpers

At launch the native shell should:

1. Create `~/Library/Application Support/PhoenixFlare/launch-buffer.json` (Mac)
   or the iOS Application Support twin.
2. Prompt mic, camera, location before the hatch word.
3. Gather bookmark URLs only from files the user can read:
   - Mac: Safari `Bookmarks.plist` / Chrome Bookmarks JSON if readable
   - iOS: user-picked `bookmarks.html` (Safari will not hand over its database)

Sources:
- helpers/macos/BookmarkBuffer.swift
- helpers/ios/PhoenixLaunchBuffer.swift

The web listen/sim pages read `launch-buffer.json` from the same folder when served locally.

Not The Sims 4. Static original rooms only. No EA assets.
