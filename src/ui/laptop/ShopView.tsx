"use client";
import { formatPrice, productById, products, type Product } from "@content/catalog";
import { useStore } from "@/state/store";
import * as act from "@/state/actions";
import { IconBack, IconPause, IconPlay } from "../icons";

function CartButton({ p }: { p: Product }) {
  const inCart = useStore((s) => s.cart.includes(p.id));
  return inCart ? (
    <button className="btn" onClick={() => useStore.getState().setTab("cart")}>In cart — view</button>
  ) : (
    <button className="btn solid" onClick={() => useStore.getState().addToCart(p.id)}>Add to cart · {formatPrice(p.priceCents)}</button>
  );
}

function PreviewButton({ p }: { p: Product }) {
  const now = useStore((s) => s.nowPlaying);
  const playing = useStore((s) => s.playing);
  const active = now?.id === p.id && playing;
  return (
    <button className="btn" aria-pressed={active} onClick={() => act.playTrack({ id: p.id, title: `${p.title} (preview)`, src: p.preview, cover: p.cover })}>
      {active ? <IconPause /> : <IconPlay />} {active ? "Pause preview" : "Play preview"}
    </button>
  );
}

function Detail({ p }: { p: Product }) {
  return (
    <div className="view">
      <button className="btn" onClick={() => useStore.getState().showProduct(null)} style={{ marginBottom: 20 }}><IconBack /> All products</button>
      <div className="detail">
        <div className="art"><img src={p.cover} alt={`Sleeve artwork for ${p.title}`} width={1200} height={1200} /></div>
        <div>
          <p className="kicker">{p.kind}</p>
          <h2>{p.title}</h2>
          <p className="lede" style={{ marginBottom: 10 }}>{p.tagline}</p>
          <p>{p.description}</p>
          <ul className="ticks">{p.details.map((d) => <li key={d}>{d}</li>)}</ul>
          <p className="price" style={{ fontSize: 28, margin: "0 0 16px" }}>{formatPrice(p.priceCents)}</p>
          <div className="row"><CartButton p={p} /><PreviewButton p={p} /></div>
        </div>
      </div>
    </div>
  );
}

export function ShopView() {
  const productId = useStore((s) => s.productId);
  const p = productId ? productById(productId) : null;
  if (p) return <Detail p={p} />;
  return (
    <div className="view">
      <p className="kicker">sounds from this room</p>
      <h3 className="display">the shop</h3>
      <p className="lede">Kits, loops and patches recorded and built down here. Instant download after checkout.</p>
      <div className="grid">
        {products.map((p) => (
          <article className="card" key={p.id}>
            <button className="art" style={{ border: 0, padding: 0 }} onClick={() => useStore.getState().showProduct(p.id)} aria-label={`${p.title} — details`}>
              <img src={p.cover} alt="" width={600} height={600} loading="lazy" />
            </button>
            <div className="row spread"><span className="meta">{p.kind}</span><span className="price">{formatPrice(p.priceCents)}</span></div>
            <h3>{p.title}</h3>
            <p>{p.tagline}</p>
            <div className="row">
              <button className="btn" onClick={() => useStore.getState().showProduct(p.id)}>Details</button>
              <CartButton p={p} />
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
