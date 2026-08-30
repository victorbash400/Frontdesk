import Link from "next/link";

export default function ExtensionPage() {
  return <main style={{ maxWidth: 640, margin: "80px auto", padding: 24 }}>
    <h1>Front Desk Browser Use</h1>
    <p>Connect your Chrome profile to Front Desk so browser tasks run in your own tabs.</p>
    <p><a href="/downloads/front-desk-extension.zip" download>Download Chrome extension</a></p>
    <ol>
      <li>Download and unzip the extension.</li>
      <li>Open chrome://extensions in the Chrome profile you want Front Desk to use.</li>
      <li>Enable Developer mode, choose Load unpacked, and select the unzipped folder.</li>
      <li>Open Front Desk in that same profile and enable Browser Use in Plugins.</li>
      <li>Keep Front Desk open. When a browser task requests a connection, approve it in the extension.</li>
    </ol>
    <p>Browser tasks need Chrome open. Meeting audio may also require the separately installed Agent Mike and Agent Ears devices; they are not included in this extension.</p>
    <Link href="/">Back to Front Desk</Link>
  </main>;
}
