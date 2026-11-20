# Desktop Goose 🪿

A small goose that waddles around your screen.

- **Left-click** to honk, **drag** to pick it up (it won't be happy).
- **Right-click** for the menu: Honk / Put out bread / Lay an egg / Shoo / Mute.
- Leave it alone and it naps and snores. Waking it is a mistake.
- It lays eggs; they hatch into goslings that follow it in a line.
- Put out bread and it fetches it. Take the bread back and it comes for you.

## Download (easiest)

Grab the latest build from the [Releases](../../releases) page.

**Windows:** unzip `DesktopGoose-Windows.zip` and run `DesktopGoose.exe`.
SmartScreen may warn about an unknown publisher: *More info → Run anyway*.

**macOS:** unzip `DesktopGoose-macOS.zip`, move `DesktopGoose.app` to Applications.
The app is unsigned, so the first time run `xattr -cr /Applications/DesktopGoose.app`
(or right-click → Open).

To quit the goose, use the menu's Shoo option or end the process in Task Manager / Activity Monitor.

## Install from source (starts at login)

Requires Python 3.9+.

```
git clone https://github.com/GuinnessStout113/desktop-goose
cd desktop-goose
./install.sh                                        # macOS
powershell -ExecutionPolicy Bypass -File install.ps1   # Windows
```

On macOS, manage it with `./goosectl start|stop|restart|status|uninstall`.
On Windows, delete `Desktop Goose.lnk` from your Startup folder to uninstall.

Or just run it once: `pip install -r requirements.txt && python goose.py`.

## Building a release

Push a tag (`git tag v1.0.0 && git push origin v1.0.0`); the GitHub Actions workflow builds
macOS and Windows packages and attaches them to the release.

## License

MIT
