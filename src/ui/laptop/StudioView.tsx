import { projects, studio } from "@content/catalog";
import { useStore } from "@/state/store";

export function StudioView() {
  return (
    <div className="view">
      <p className="kicker">{studio.tagline}</p>
      <h3 className="display">after midnight,<br />under the house</h3>
      <p className="lede">{studio.intro}</p>
      <ul className="pill-row" aria-label="Services">
        {studio.services.map((s) => <li key={s}>{s}</li>)}
      </ul>
      <div className="row spread">
        <h3 className="section-h">featured projects</h3>
        <button className="btn" onClick={() => useStore.getState().setTab("listen")}>Hear the room</button>
      </div>
      <div className="grid">
        {projects.map((p) => (
          <article className="card" key={p.id}>
            <div className="art"><img src={p.cover} alt={`Sleeve for ${p.title}`} loading="lazy" width={600} height={600} /></div>
            <p className="meta">{p.year} · {p.role}</p>
            <h3>{p.title}</h3>
            <p>{p.blurb}</p>
          </article>
        ))}
      </div>
    </div>
  );
}
