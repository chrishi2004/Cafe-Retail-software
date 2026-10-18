import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { CheckCircle2, Coffee, Pencil, Plus, RefreshCw, Search, UtensilsCrossed } from "lucide-react";

import {
  createMenuCategory,
  createMenuItem,
  listMenuCategories,
  listMenuItems,
  setMenuItemAvailability,
  type MenuCategory,
  type MenuItem,
  type MenuItemInput,
  type PreparationArea,
  updateMenuCategory,
  updateMenuItem,
} from "../api/cafe";
import { ApiError } from "../api/client";
import { listProducts } from "../api/masterData";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, LoadingState } from "../components/ui";
import type { Product } from "../types";

const PREPARATION_AREAS: PreparationArea[] = ["kitchen", "beverage", "counter", "none"];

function messageFrom(error: unknown): string {
  return error instanceof ApiError ? error.message : "Cafe menu operation failed.";
}

function emptyItem(categoryId = 0): MenuItemInput {
  return {
    branch_id: null,
    category_id: categoryId,
    product_id: null,
    name: "",
    description: null,
    image_reference: null,
    selling_price: "0.00",
    preparation_area: "none",
    available: true,
    is_active: true,
    display_order: 0,
  };
}

export function CafeMenuPage() {
  const { token, user } = useAuth();
  const canAdmin = user?.server_role === "super_admin" || user?.server_role === "admin";
  const [categories, setCategories] = useState<MenuCategory[]>([]);
  const [items, setItems] = useState<MenuItem[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [categoryName, setCategoryName] = useState("");
  const [editingCategory, setEditingCategory] = useState<MenuCategory | null>(null);
  const [editingItem, setEditingItem] = useState<MenuItem | null>(null);
  const [itemForm, setItemForm] = useState<MenuItemInput>(() => emptyItem());

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const [categoryRows, itemRows, productRows] = await Promise.all([
        listMenuCategories(token),
        listMenuItems(token, search),
        listProducts(token),
      ]);
      setCategories(categoryRows);
      setItems(itemRows);
      setProducts(productRows.filter((row) => row.is_active));
      if (!itemForm.category_id && categoryRows[0]) {
        setItemForm((current) => ({ ...current, category_id: categoryRows[0].id }));
      }
    } catch (loadError) {
      setError(messageFrom(loadError));
    } finally {
      setLoading(false);
    }
  }, [token, search, itemForm.category_id]);

  useEffect(() => {
    void load();
  }, [load]);

  const categoryNames = useMemo(
    () => new Map(categories.map((category) => [category.id, category.name])),
    [categories],
  );

  function startEditCategory(category: MenuCategory) {
    setEditingCategory(category);
    setCategoryName(category.name);
    setError(null);
    setSuccess(null);
  }

  async function saveCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !canAdmin || !categoryName.trim()) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      if (editingCategory) {
        await updateMenuCategory(token, editingCategory.id, {
          branch_id: editingCategory.branch_id,
          name: categoryName.trim(),
          display_order: editingCategory.display_order,
          is_active: editingCategory.is_active,
        });
        setSuccess("Menu category updated.");
      } else {
        await createMenuCategory(token, {
          branch_id: null,
          name: categoryName.trim(),
          display_order: categories.length + 1,
          is_active: true,
        });
        setSuccess("Menu category created.");
      }
      setCategoryName("");
      setEditingCategory(null);
      await load();
    } catch (saveError) {
      setError(messageFrom(saveError));
    } finally {
      setSaving(false);
    }
  }

  function startNewItem() {
    setEditingItem(null);
    setItemForm(emptyItem(categories[0]?.id ?? 0));
    setError(null);
    setSuccess(null);
  }

  function startEditItem(item: MenuItem) {
    setEditingItem(item);
    setItemForm({
      branch_id: item.branch_id,
      category_id: item.category_id,
      product_id: item.product_id,
      name: item.name,
      description: item.description,
      image_reference: item.image_reference,
      selling_price: item.selling_price,
      preparation_area: item.preparation_area,
      available: item.available,
      is_active: item.is_active,
      display_order: item.display_order,
    });
    setError(null);
    setSuccess(null);
  }

  async function saveItem(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !canAdmin || !itemForm.category_id || !itemForm.name.trim()) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      if (editingItem) {
        await updateMenuItem(token, editingItem.id, {
          ...itemForm,
          name: itemForm.name.trim(),
          expected_version: editingItem.version,
        });
        setSuccess("Menu item updated.");
      } else {
        await createMenuItem(token, { ...itemForm, name: itemForm.name.trim() });
        setSuccess("Menu item created.");
      }
      startNewItem();
      await load();
    } catch (saveError) {
      setError(messageFrom(saveError));
    } finally {
      setSaving(false);
    }
  }

  async function toggleAvailability(item: MenuItem) {
    if (!token || !canAdmin) return;
    setSaving(true);
    setError(null);
    try {
      await setMenuItemAvailability(token, item.id, !item.available, item.version);
      setSuccess(`${item.name} is now ${item.available ? "unavailable" : "available"}.`);
      await load();
    } catch (toggleError) {
      setError(messageFrom(toggleError));
    } finally {
      setSaving(false);
    }
  }

  if (loading && !categories.length && !items.length) return <LoadingState label="Loading Cafe menu" />;

  return (
    <section className="page-stack">
      <div className="page-header">
        <div>
          <p className="eyebrow">Cafe menu administration</p>
          <h2>Menu Management</h2>
          <p className="page-description">
            Company-scoped Cafe menu policy. Prices are customer display prices; P4 keeps current billing Non-GST unless the guarded activation workflow changes it.
          </p>
        </div>
        <button className="action-button secondary" type="button" onClick={() => void load()} disabled={loading || saving}>
          <RefreshCw size={17} aria-hidden="true" /> Refresh
        </button>
      </div>

      {error ? <ErrorState message={error} /> : null}
      {success ? <div className="state-panel success"><CheckCircle2 size={20} aria-hidden="true" /><p>{success}</p></div> : null}

      <div className="dashboard-grid">
        <article className="panel">
          <div className="panel-header">
            <div><p className="eyebrow">Categories</p><h3>{categories.length} sections</h3></div>
            <Coffee size={21} aria-hidden="true" />
          </div>
          {categories.length ? (
            <div className="data-table-shell">
              <table>
                <thead><tr><th>Order</th><th>Name</th><th>Scope</th>{canAdmin ? <th>Action</th> : null}</tr></thead>
                <tbody>
                  {categories.map((category) => (
                    <tr key={category.id}>
                      <td>{category.display_order}</td>
                      <td>{category.name}</td>
                      <td>{category.branch_id ? `Branch ${category.branch_id}` : "All Cafe branches"}</td>
                      {canAdmin ? <td><button className="table-action" type="button" onClick={() => startEditCategory(category)}><Pencil size={15} /> Edit</button></td> : null}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="page-description">No menu categories yet.</p>}

          {canAdmin ? (
            <form className="master-form" onSubmit={saveCategory}>
              <label>
                {editingCategory ? "Edit category" : "New category"}
                <input value={categoryName} onChange={(event) => setCategoryName(event.target.value)} placeholder="Hot Beverages" disabled={saving} />
              </label>
              <div className="form-actions">
                <button className="action-button primary" type="submit" disabled={saving || !categoryName.trim()}>
                  <Plus size={16} /> {editingCategory ? "Save category" : "Add category"}
                </button>
                {editingCategory ? <button className="action-button secondary" type="button" onClick={() => { setEditingCategory(null); setCategoryName(""); }}>Cancel</button> : null}
              </div>
            </form>
          ) : null}
        </article>

        {canAdmin ? (
          <form className="panel master-form" onSubmit={saveItem}>
            <div className="panel-header">
              <div><p className="eyebrow">Item editor</p><h3>{editingItem ? `Edit ${editingItem.name}` : "Add menu item"}</h3></div>
              <UtensilsCrossed size={21} aria-hidden="true" />
            </div>
            <label>Item name<input value={itemForm.name} onChange={(event) => setItemForm({ ...itemForm, name: event.target.value })} disabled={saving} /></label>
            <label>
              Category
              <select value={itemForm.category_id || ""} onChange={(event) => setItemForm({ ...itemForm, category_id: Number(event.target.value) })} disabled={saving}>
                <option value="" disabled>Select category</option>
                {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
              </select>
            </label>
            <label>
              Optional Cafe product link
              <select value={itemForm.product_id ?? ""} onChange={(event) => setItemForm({ ...itemForm, product_id: event.target.value ? Number(event.target.value) : null })} disabled={saving}>
                <option value="">No product link</option>
                {products.map((product) => <option key={product.id} value={product.id}>{product.name} ({product.sku})</option>)}
              </select>
            </label>
            <label>Selling price<input type="number" min="0" step="0.01" value={itemForm.selling_price} onChange={(event) => setItemForm({ ...itemForm, selling_price: event.target.value })} disabled={saving} /></label>
            <label>
              Preparation area
              <select value={itemForm.preparation_area} onChange={(event) => setItemForm({ ...itemForm, preparation_area: event.target.value as PreparationArea })} disabled={saving}>
                {PREPARATION_AREAS.map((area) => <option key={area} value={area}>{area}</option>)}
              </select>
            </label>
            <label>Description<textarea value={itemForm.description ?? ""} onChange={(event) => setItemForm({ ...itemForm, description: event.target.value || null })} disabled={saving} /></label>
            <label>Image reference<input value={itemForm.image_reference ?? ""} onChange={(event) => setItemForm({ ...itemForm, image_reference: event.target.value || null })} placeholder="Optional URL or asset reference" disabled={saving} /></label>
            <label>Display order<input type="number" min="0" value={itemForm.display_order} onChange={(event) => setItemForm({ ...itemForm, display_order: Number(event.target.value) })} disabled={saving} /></label>
            <div className="form-actions">
              <button className="action-button primary" type="submit" disabled={saving || !itemForm.category_id || !itemForm.name.trim()}>{editingItem ? "Save item" : "Create item"}</button>
              {editingItem ? <button className="action-button secondary" type="button" onClick={startNewItem}>Cancel</button> : null}
            </div>
          </form>
        ) : (
          <article className="panel"><p className="page-description">Your role can view menu availability but cannot change Cafe menu administration.</p></article>
        )}
      </div>

      <article className="panel wide">
        <div className="panel-header">
          <div><p className="eyebrow">Sellable menu</p><h3>{items.length} items</h3></div>
          <label className="search-field"><Search size={17} aria-hidden="true" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search menu" /></label>
        </div>
        {items.length ? (
          <div className="data-table-shell">
            <table>
              <thead><tr><th>Order</th><th>Item</th><th>Category</th><th>Price</th><th>Prep</th><th>Product</th><th>Availability</th>{canAdmin ? <th>Actions</th> : null}</tr></thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>{item.display_order}</td>
                    <td><strong>{item.name}</strong><div className="muted-text">v{item.version}</div></td>
                    <td>{categoryNames.get(item.category_id) ?? `#${item.category_id}`}</td>
                    <td>₹{Number(item.selling_price).toFixed(2)}</td>
                    <td>{item.preparation_area}</td>
                    <td>{item.product_id ? `#${item.product_id}` : "Menu only"}</td>
                    <td><span className={`status-badge ${item.available ? "success" : "warning"}`}>{item.available ? "Available" : "Unavailable"}</span></td>
                    {canAdmin ? (
                      <td>
                        <div className="table-actions">
                          <button className="table-action" type="button" onClick={() => startEditItem(item)}><Pencil size={15} /> Edit</button>
                          <button className="table-action" type="button" onClick={() => void toggleAvailability(item)} disabled={saving}>{item.available ? "Pause" : "Enable"}</button>
                        </div>
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <p className="page-description">No Cafe menu items match this view.</p>}
      </article>
    </section>
  );
}
