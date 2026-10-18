import { useMemo, useState } from "react";

import type { PublicMenu } from "../api/publicCafeClient";

function price(value: string): string {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(Number(value));
}

export function CafeMenuList({
  menu,
  acceptingItems,
  quantity,
  changeQuantity,
}: {
  menu: PublicMenu;
  acceptingItems: boolean;
  quantity: (id: string) => number;
  changeQuantity: (id: string, delta: number) => void;
}) {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return menu.items.filter((item) =>
      (category === "all" || item.category_public_id === category) &&
      (!needle || `${item.name} ${item.description ?? ""}`.toLowerCase().includes(needle)),
    );
  }, [category, menu.items, search]);

  return (
    <section className="page-stack" aria-label="Cafe menu">
      <div className="filter-bar" style={{ flexWrap: "wrap" }}>
        <div className="search-shell" style={{ width: "100%" }}>
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search the menu" aria-label="Search menu" />
        </div>
        <div className="filter-actions" style={{ justifyContent: "flex-start", overflowX: "auto", width: "100%", flexWrap: "nowrap" }}>
          <button type="button" className="filter-chip" onClick={() => setCategory("all")}>All</button>
          {menu.categories.map((row) => <button type="button" className="filter-chip" key={row.public_id} onClick={() => setCategory(row.public_id)}>{row.name}</button>)}
        </div>
      </div>
      <div className="metric-grid" style={{ gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))" }}>
        {visible.map((item) => {
          const count = quantity(item.public_id);
          return (
            <article className="metric-card" key={item.public_id} style={{ minHeight: 0 }}>
              <h3>{item.name}</h3>
              <p style={{ marginTop: 6 }}>{item.description ?? ""}</p>
              <strong>{price(item.selling_price)}</strong>
              {!item.available ? <span>Currently unavailable</span> : null}
              {acceptingItems && item.available ? (
                count ? <div className="page-actions" style={{ marginTop: 12 }}><button type="button" className="action-button secondary" onClick={() => changeQuantity(item.public_id, -1)}>−</button><strong style={{ margin: 0 }}>{count}</strong><button type="button" className="action-button secondary" onClick={() => changeQuantity(item.public_id, 1)}>+</button></div> : <button type="button" className="action-button secondary" style={{ marginTop: 12, width: "100%" }} onClick={() => changeQuantity(item.public_id, 1)}>Add</button>
              ) : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}
