import Link from "next/link";

const features = [
  {
    icon: "voice",
    title: "Natural AI Voice",
    body: "Create clear narrated audio that feels suited for chapters, notes, and long-form study material."
  },
  {
    icon: "bolt",
    title: "Fast Conversion",
    body: "Upload documents, index content, ask questions, and generate listenable summaries from one focused studio."
  },
  {
    icon: "download",
    title: "Download & Listen Anywhere",
    body: "Turn answers and document scripts into portable audio for review sessions away from the screen."
  }
];

const waveform = [38, 58, 44, 72, 50, 86, 62, 46, 76, 54, 92, 64, 48, 70, 42, 60, 36, 52];

function LogoMark() {
  return (
    <span className="logoMark" aria-hidden="true">
      <span />
    </span>
  );
}

function MiniIcon({ type }: { type: string }) {
  return <span className={`miniIcon ${type}`} aria-hidden="true" />;
}

export default function LandingPage() {
  return (
    <main className="siteShell">
      <nav className="siteHeader" aria-label="Main navigation">
        <div className="siteNav">
          <Link className="siteBrand" href="/">
            <LogoMark />
            <strong>AI Audiobook</strong>
          </Link>
          <div className="siteLinks">
            <a href="#features">Features</a>
            <a href="#studio">Studio</a>
            <Link className="navAction" href="/workspace">Open app</Link>
          </div>
        </div>
      </nav>

      <section className="landingHero">
        <div className="heroCopy">
          <p className="heroKicker">AI audiobook studio</p>
          <h1>Create audiobooks from your documents</h1>
          <p className="heroLead">
            Upload PDFs, notes, or links. Ask questions with citations and
            generate clean narration in seconds.
          </p>
          <div className="heroActions">
            <Link className="heroPrimary" href="/workspace">Open Studio</Link>
            <a className="heroSecondary" href="#studio">View workflow</a>
          </div>
        </div>

        <div className="heroVisualWrap" aria-label="Audiobook player preview">
          <div className="audiobookPlayer">
            <div className="playerTop">
              <div className="bookCover">
                <span className="coverOrb" />
                <span className="coverLine wide" />
                <span className="coverLine" />
              </div>
              <div>
                <span className="playerBadge">Ready</span>
                <h2 title="Document Narration">Document Narration</h2>
                <p>Warm AI voice</p>
              </div>
            </div>

            <div className="waveform" aria-hidden="true">
              {waveform.map((height, index) => (
                <span key={`${height}-${index}`} style={{ height: `${height}%` }} />
              ))}
            </div>

            <div className="playerControls">
              <button aria-label="Play preview" className="playButton">
                <span />
              </button>
              <div className="progressTrack">
                <span />
              </div>
              <strong>03:42</strong>
            </div>
          </div>
        </div>
      </section>

      <section id="studio" className="toolPreview">
        <div className="sectionHeader">
          <p className="heroKicker">Workflow</p>
          <h2>A focused path from source material to audio.</h2>
        </div>
        <div className="studioGrid">
          <div className="studioPanel">
            <span className="panelNumber">01</span>
            <h3>Add source material</h3>
            <p>Bring in PDFs, notes, documents, images, CSVs, Markdown, or a study URL.</p>
          </div>
          <div className="studioPanel">
            <span className="panelNumber">02</span>
            <h3>Ask with context</h3>
            <p>Retrieve cited answers from indexed sources before turning the response into audio.</p>
          </div>
          <div className="studioPanel highlight">
            <span className="panelNumber">03</span>
            <h3>Generate audiobook audio</h3>
            <p>Build scripts and listen to polished narration directly in the workspace.</p>
            <Link className="inlineButton" href="/workspace">Open workspace</Link>
          </div>
        </div>
      </section>

      <section id="features" className="featureBand">
        {features.map((feature) => (
          <article className="featureCard" key={feature.title}>
            <MiniIcon type={feature.icon} />
            <h3>{feature.title}</h3>
            <p>{feature.body}</p>
          </article>
        ))}
      </section>
    </main>
  );
}
