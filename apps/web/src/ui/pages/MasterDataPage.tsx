import { FormEvent, type ReactNode, useCallback, useEffect, useState } from "react";
import { Edit3, Plus, RotateCw, Search } from "lucide-react";

import { listTaxRates } from "../api/businessSettings";
import { ApiError } from "../api/client";
import {
  createBranch,
  createCategory,
  createProduct,
  createSupplier,
  deactivateProduct,
  listBranches,
  listCategories,
  listProducts,
  listSuppliers,
  updateBranch,
  updateCategory,
  updateProduct,
  updateSupplier,
} from "../api/masterData";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, ErrorState, LoadingState, MetricCard } from "../components/ui";
import type {
  Branch,
  BranchPayload,
  Category,
  CategoryPayload,
  Product,
  ProductPayload,
  RouteKey,
  Supplier,
  SupplierPayload,
  TaxRate,
} from "../types";

type MasterRouteKey = "products" | "suppliers" | "categories" | "branches";

export function isMasterDataRoute(routeKey: RouteKey): routeKey is MasterRouteKey {
  return ["products", "suppliers", "categories", "branches"].includes(routeKey);
}

const emptyProductForm: ProductPayload = {
  sku: "",
  name: "",
  description: "",
  category_id: 0,
  supplier_id: 0,
  gst_rate_id: null,
  unit_cost: "0.00",
  selling_price: "0.00",
  hsn_sac_code: "",
  cess_rate_percent: "0.00",
  primary_barcode: "",
  unit_of_measure: "pcs",
  mrp: "",
  brand: "",
  manufacturer: "",
  item_type: "goods",
  batch_tracking_enabled: false,
  serial_tracking_enabled: false,
  expiry_tracking_enabled: false,
  reorder_threshold: "0.00",
  target_stock_level: "0.00",
  is_active: true,
};

const emptySupplierForm: SupplierPayload = {
  name: "",
  contact_person: "",
  email: "",
  phone: "",
  address: "",
  payment_terms: "",
  lead_time_days: 7,
  is_active: true,
};

const emptyCategoryForm: CategoryPayload = {
  name: "",
  description: "",
};

const emptyBranchForm: BranchPayload = {
  name: "",
  address: "",
  city: "",
  manager_name: "",
  is_active: true,
};

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "Could not complete the request. Check that the backend is running.";
}

function cleanOptional(value: string | null): string | null {
  const trimmed = (value ?? "").trim();
  return trimmed ? trimmed : null;
}

function PageToolbar({
  search,
  setSearch,
  includeInactive,
  setIncludeInactive,
  onRefresh,
  placeholder = "Search master data",
  showInactiveToggle = true,
}: {
  search: string;
  setSearch: (value: string) => void;
  includeInactive: boolean;
  setIncludeInactive: (value: boolean) => void;
  onRefresh: () => void;
  placeholder?: string;
  showInactiveToggle?: boolean;
}) {
  return (
    <div className="filter-bar">
      <div className="search-shell">
        <Search aria-hidden="true" size={16} />
        <input
          aria-label="Search master data"
          onChange={(event) => setSearch(event.target.value)}
          placeholder={placeholder}
          type="search"
          value={search}
        />
      </div>
      <div className="filter-actions">
        {showInactiveToggle ? (
          <label className="checkbox-row compact">
            <input
              checked={includeInactive}
              onChange={(event) => setIncludeInactive(event.target.checked)}
              type="checkbox"
            />
            <span>Include inactive</span>
          </label>
        ) : null}
        <button className="filter-chip" onClick={onRefresh} type="button">
          <RotateCw aria-hidden="true" size={15} />
          Refresh
        </button>
      </div>
    </div>
  );
}

function AdminGate({ isAdmin }: { isAdmin: boolean }) {
  if (isAdmin) {
    return null;
  }
  return (
    <EmptyState
      title="Admin permission required"
      message="You can inspect master data, but create and edit actions are restricted by the backend."
    />
  );
}

export function MasterDataPage({ routeKey }: { routeKey: MasterRouteKey }) {
  if (routeKey === "products") {
    return <ProductsPage />;
  }
  if (routeKey === "suppliers") {
    return <SuppliersPage />;
  }
  if (routeKey === "categories") {
    return <CategoriesPage />;
  }
  return <BranchesPage />;
}

function ProductsPage() {
  const { token, user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [taxRates, setTaxRates] = useState<TaxRate[]>([]);
  const [form, setForm] = useState<ProductPayload>(emptyProductForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState(0);
  const [supplierFilter, setSupplierFilter] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [productRows, categoryRows, supplierRows, taxRateRows] = await Promise.all([
        listProducts(token, {
          search,
          includeInactive,
          categoryId: categoryFilter || undefined,
          supplierId: supplierFilter || undefined,
        }),
        listCategories(token),
        listSuppliers(token, { includeInactive: true }),
        listTaxRates(token, true),
      ]);
      setProducts(productRows);
      setCategories(categoryRows);
      setSuppliers(supplierRows);
      setTaxRates(taxRateRows);
      setForm((current) => ({
        ...current,
        category_id: current.category_id || categoryRows[0]?.id || 0,
        supplier_id: current.supplier_id || supplierRows[0]?.id || 0,
        gst_rate_id: current.gst_rate_id ?? taxRateRows.find((rate) => rate.is_active)?.id ?? null,
      }));
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, [categoryFilter, includeInactive, search, supplierFilter, token]);

  useEffect(() => {
    void load();
  }, [load]);

  const resetForm = () => {
    setEditingId(null);
    setForm({
      ...emptyProductForm,
      category_id: categories[0]?.id || 0,
      supplier_id: suppliers[0]?.id || 0,
      gst_rate_id: taxRates.find((rate) => rate.is_active)?.id ?? null,
    });
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token || !isAdmin) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const payload = {
        ...form,
        sku: form.sku.trim().toUpperCase(),
        name: form.name.trim(),
        description: cleanOptional(form.description),
        gst_rate_id: form.gst_rate_id || null,
        hsn_sac_code: cleanOptional(form.hsn_sac_code)?.toUpperCase() ?? null,
        primary_barcode: cleanOptional(form.primary_barcode)?.toUpperCase() ?? null,
        mrp: cleanOptional(form.mrp),
        brand: cleanOptional(form.brand),
        manufacturer: cleanOptional(form.manufacturer),
        unit_of_measure: form.unit_of_measure.trim().toLowerCase(),
      };
      if (editingId) {
        await updateProduct(token, editingId, payload);
      } else {
        await createProduct(token, payload);
      }
      resetForm();
      await load();
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setSaving(false);
    }
  };

  const editProduct = (product: Product) => {
    setEditingId(product.id);
    setForm({
      sku: product.sku,
      name: product.name,
      description: product.description ?? "",
      category_id: product.category_id,
      supplier_id: product.supplier_id,
      gst_rate_id: product.gst_rate_id,
      unit_cost: product.unit_cost,
      selling_price: product.selling_price,
      hsn_sac_code: product.hsn_sac_code ?? "",
      cess_rate_percent: product.cess_rate_percent,
      primary_barcode: product.primary_barcode ?? "",
      unit_of_measure: product.unit_of_measure,
      mrp: product.mrp ?? "",
      brand: product.brand ?? "",
      manufacturer: product.manufacturer ?? "",
      item_type: product.item_type,
      batch_tracking_enabled: product.batch_tracking_enabled,
      serial_tracking_enabled: product.serial_tracking_enabled,
      expiry_tracking_enabled: product.expiry_tracking_enabled,
      reorder_threshold: product.reorder_threshold,
      target_stock_level: product.target_stock_level,
      is_active: product.is_active,
    });
  };

  const handleDeactivate = async (product: Product) => {
    if (!token || !isAdmin) {
      return;
    }
    setError(null);
    try {
      await deactivateProduct(token, product.id);
      await load();
      if (editingId === product.id) {
        resetForm();
      }
    } catch (deactivateError) {
      setError(errorMessage(deactivateError));
    }
  };

  const activeCount = products.filter((product) => product.is_active).length;

  return (
    <section className="page-stack">
      <MasterHeader
        description="Create and maintain product SKUs with category, supplier, cost, selling price, and reorder settings."
        title="Product management"
      />
      <PageToolbar
        includeInactive={includeInactive}
        onRefresh={load}
        placeholder="Search product, SKU, barcode, category, supplier"
        search={search}
        setIncludeInactive={setIncludeInactive}
        setSearch={setSearch}
      />
      <div className="filter-bar compact-filter">
        <select
          aria-label="Filter products by category"
          onChange={(event) => setCategoryFilter(Number(event.target.value))}
          value={categoryFilter}
        >
          <option value={0}>All categories</option>
          {categories.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
        </select>
        <select
          aria-label="Filter products by supplier"
          onChange={(event) => setSupplierFilter(Number(event.target.value))}
          value={supplierFilter}
        >
          <option value={0}>All suppliers</option>
          {suppliers.map((supplier) => (
            <option key={supplier.id} value={supplier.id}>
              {supplier.name}
            </option>
          ))}
        </select>
      </div>
      <section className="metric-grid">
        <MetricCard metric={{ label: "Products Loaded", value: String(products.length), detail: "Current filter result", tone: "blue" }} />
        <MetricCard metric={{ label: "Active Products", value: String(activeCount), detail: "Shown by default in sales selection", tone: "green" }} />
        <MetricCard metric={{ label: "Barcoded", value: String(products.filter((product) => product.primary_barcode).length), detail: "Ready for POS scan lookup", tone: "amber" }} />
        <MetricCard metric={{ label: "GST Rates", value: String(taxRates.length), detail: "Tax mapping options", tone: "slate" }} />
      </section>
      {error ? <ErrorState message={error} title="Product action failed" /> : null}
      <section className="master-grid">
        <article className="panel wide">
          <PanelTitle title="Products" />
          {loading ? <LoadingState label="Loading products" /> : null}
          {!loading && products.length === 0 ? (
            <EmptyState title="No products found" message="Try a different search or create the first product." />
          ) : null}
          {!loading && products.length > 0 ? (
            <div className="table-shell">
              <table>
                <thead>
                  <tr>
                    <th>SKU</th>
                    <th>Product</th>
                    <th>Barcode</th>
                    <th>HSN/GST</th>
                    <th>Brand/Unit</th>
                    <th>Price</th>
                    <th>Stock</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {products.map((product) => (
                    <tr key={product.id}>
                      <td>{product.sku}</td>
                      <td>
                        <strong>{product.name}</strong>
                        <span>{product.category_name} / {product.supplier_name}</span>
                      </td>
                      <td>{product.primary_barcode ?? "Not set"}</td>
                      <td>
                        <strong>{product.hsn_sac_code ?? "No HSN"}</strong>
                        <span>{product.gst_rate_name ?? "No GST rate"}</span>
                      </td>
                      <td>
                        <strong>{product.brand ?? "No brand"}</strong>
                        <span>{product.unit_of_measure}</span>
                      </td>
                      <td>
                        <strong>{product.selling_price}</strong>
                        <span>MRP {product.mrp ?? "Not set"}</span>
                      </td>
                      <td>
                        <strong>{product.stock_status}</strong>
                        <span>{product.total_quantity_on_hand} on hand</span>
                      </td>
                      <td>
                        <span className={product.is_active ? "status-badge ok" : "status-badge warning"}>
                          {product.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td>
                        <div className="table-actions">
                          <button disabled={!isAdmin} onClick={() => editProduct(product)} type="button">
                            <Edit3 aria-hidden="true" size={14} />
                            Edit
                          </button>
                          <button disabled={!isAdmin || !product.is_active} onClick={() => handleDeactivate(product)} type="button">
                            Deactivate
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </article>
        <aside className="panel">
          <AdminGate isAdmin={Boolean(isAdmin)} />
          {isAdmin ? (
            <form className="master-form" onSubmit={handleSubmit}>
              <PanelTitle title={editingId ? "Edit product" : "Create product"} />
              <label>SKU<input required value={form.sku} onChange={(event) => setForm({ ...form, sku: event.target.value })} /></label>
              <label>Name<input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
              <label>Description<textarea value={form.description ?? ""} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label>
              <label>Category<select required value={form.category_id} onChange={(event) => setForm({ ...form, category_id: Number(event.target.value) })}>
                <option value={0}>Select category</option>
                {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
              </select></label>
              <label>Supplier<select required value={form.supplier_id} onChange={(event) => setForm({ ...form, supplier_id: Number(event.target.value) })}>
                <option value={0}>Select supplier</option>
                {suppliers.map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}
              </select></label>
              <div className="form-grid two">
                <label>HSN/SAC<input value={form.hsn_sac_code ?? ""} onChange={(event) => setForm({ ...form, hsn_sac_code: event.target.value })} /></label>
                <label>GST rate<select value={form.gst_rate_id ?? 0} onChange={(event) => setForm({ ...form, gst_rate_id: Number(event.target.value) || null })}>
                  <option value={0}>No GST rate</option>
                  {taxRates.map((rate) => <option key={rate.id} value={rate.id}>{rate.name}</option>)}
                </select></label>
                <label>Barcode<input value={form.primary_barcode ?? ""} onChange={(event) => setForm({ ...form, primary_barcode: event.target.value })} /></label>
                <label>Unit<select value={form.unit_of_measure} onChange={(event) => setForm({ ...form, unit_of_measure: event.target.value })}>
                  <option value="pcs">pcs</option>
                  <option value="kg">kg</option>
                  <option value="g">g</option>
                  <option value="l">l</option>
                  <option value="ml">ml</option>
                  <option value="pack">pack</option>
                  <option value="box">box</option>
                </select></label>
                <label>Brand<input value={form.brand ?? ""} onChange={(event) => setForm({ ...form, brand: event.target.value })} /></label>
                <label>Manufacturer<input value={form.manufacturer ?? ""} onChange={(event) => setForm({ ...form, manufacturer: event.target.value })} /></label>
                <label>Unit cost<input min="0" step="0.01" type="number" value={form.unit_cost} onChange={(event) => setForm({ ...form, unit_cost: event.target.value })} /></label>
                <label>Selling price<input min="0" step="0.01" type="number" value={form.selling_price} onChange={(event) => setForm({ ...form, selling_price: event.target.value })} /></label>
                <label>MRP<input min="0" step="0.01" type="number" value={form.mrp ?? ""} onChange={(event) => setForm({ ...form, mrp: event.target.value })} /></label>
                <label>Cess %<input min="0" step="0.01" type="number" value={form.cess_rate_percent} onChange={(event) => setForm({ ...form, cess_rate_percent: event.target.value })} /></label>
                <label>Reorder threshold<input min="0" step="0.01" type="number" value={form.reorder_threshold} onChange={(event) => setForm({ ...form, reorder_threshold: event.target.value })} /></label>
                <label>Target stock<input min="0" step="0.01" type="number" value={form.target_stock_level} onChange={(event) => setForm({ ...form, target_stock_level: event.target.value })} /></label>
                <label>Item type<select value={form.item_type} onChange={(event) => setForm({ ...form, item_type: event.target.value as ProductPayload["item_type"] })}>
                  <option value="goods">Goods</option>
                  <option value="service">Service</option>
                </select></label>
              </div>
              <label className="checkbox-row"><input checked={form.batch_tracking_enabled} onChange={(event) => setForm({ ...form, batch_tracking_enabled: event.target.checked })} type="checkbox" /> Batch tracking</label>
              <label className="checkbox-row"><input checked={form.serial_tracking_enabled} onChange={(event) => setForm({ ...form, serial_tracking_enabled: event.target.checked })} type="checkbox" /> Serial tracking</label>
              <label className="checkbox-row"><input checked={form.expiry_tracking_enabled} onChange={(event) => setForm({ ...form, expiry_tracking_enabled: event.target.checked })} type="checkbox" /> Expiry tracking</label>
              <label className="checkbox-row"><input checked={form.is_active} onChange={(event) => setForm({ ...form, is_active: event.target.checked })} type="checkbox" /> Active product</label>
              <FormButtons editing={Boolean(editingId)} onCancel={resetForm} saving={saving} />
            </form>
          ) : null}
        </aside>
      </section>
    </section>
  );
}

function SuppliersPage() {
  const { token, user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [form, setForm] = useState<SupplierPayload>(emptySupplierForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      setSuppliers(await listSuppliers(token, { search, includeInactive }));
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, [includeInactive, search, token]);

  useEffect(() => {
    void load();
  }, [load]);

  const resetForm = () => {
    setEditingId(null);
    setForm(emptySupplierForm);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token || !isAdmin) return;
    setSaving(true);
    setError(null);
    const payload: SupplierPayload = {
      ...form,
      name: form.name.trim(),
      contact_person: cleanOptional(form.contact_person),
      email: cleanOptional(form.email),
      phone: cleanOptional(form.phone),
      address: cleanOptional(form.address),
      payment_terms: cleanOptional(form.payment_terms),
    };
    try {
      if (editingId) {
        await updateSupplier(token, editingId, payload);
      } else {
        await createSupplier(token, payload);
      }
      resetForm();
      await load();
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setSaving(false);
    }
  };

  const editSupplier = (supplier: Supplier) => {
    setEditingId(supplier.id);
    setForm({
      name: supplier.name,
      contact_person: supplier.contact_person ?? "",
      email: supplier.email ?? "",
      phone: supplier.phone ?? "",
      address: supplier.address ?? "",
      payment_terms: supplier.payment_terms ?? "",
      lead_time_days: supplier.lead_time_days,
      is_active: supplier.is_active,
    });
  };

  return (
    <section className="page-stack">
      <MasterHeader
        description="Maintain supplier contact details, payment terms, lead times, and active status for purchasing workflows."
        title="Supplier management"
      />
      <PageToolbar
        includeInactive={includeInactive}
        onRefresh={load}
        search={search}
        setIncludeInactive={setIncludeInactive}
        setSearch={setSearch}
      />
      <section className="metric-grid">
        <MetricCard metric={{ label: "Suppliers Loaded", value: String(suppliers.length), detail: "Current filter result", tone: "blue" }} />
        <MetricCard metric={{ label: "Active Suppliers", value: String(suppliers.filter((item) => item.is_active).length), detail: "Available by default", tone: "green" }} />
        <MetricCard metric={{ label: "Lead Time Field", value: "Ready", detail: "Feeds reorder logic", tone: "amber" }} />
        <MetricCard metric={{ label: "Admin Writes", value: isAdmin ? "Enabled" : "Locked", detail: "Backend enforced", tone: "slate" }} />
      </section>
      {error ? <ErrorState message={error} title="Supplier action failed" /> : null}
      <section className="master-grid">
        <article className="panel wide">
          <PanelTitle title="Suppliers" />
          {loading ? <LoadingState label="Loading suppliers" /> : null}
          {!loading && suppliers.length === 0 ? <EmptyState title="No suppliers found" message="Try another search or create a supplier." /> : null}
          {!loading && suppliers.length > 0 ? (
            <div className="table-shell">
              <table>
                <thead><tr><th>Name</th><th>Contact</th><th>Email</th><th>Lead Time</th><th>Status</th><th>Actions</th></tr></thead>
                <tbody>
                  {suppliers.map((supplier) => (
                    <tr key={supplier.id}>
                      <td>{supplier.name}</td>
                      <td>{supplier.contact_person ?? "Not set"}</td>
                      <td>{supplier.email ?? "Not set"}</td>
                      <td>{supplier.lead_time_days} days</td>
                      <td>{supplier.is_active ? "Active" : "Inactive"}</td>
                      <td><div className="table-actions"><button disabled={!isAdmin} onClick={() => editSupplier(supplier)} type="button"><Edit3 aria-hidden="true" size={14} />Edit</button></div></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </article>
        <aside className="panel">
          <AdminGate isAdmin={Boolean(isAdmin)} />
          {isAdmin ? (
            <form className="master-form" onSubmit={handleSubmit}>
              <PanelTitle title={editingId ? "Edit supplier" : "Create supplier"} />
              <label>Name<input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
              <label>Contact person<input value={form.contact_person ?? ""} onChange={(event) => setForm({ ...form, contact_person: event.target.value })} /></label>
              <label>Email<input type="email" value={form.email ?? ""} onChange={(event) => setForm({ ...form, email: event.target.value })} /></label>
              <label>Phone<input value={form.phone ?? ""} onChange={(event) => setForm({ ...form, phone: event.target.value })} /></label>
              <label>Address<textarea value={form.address ?? ""} onChange={(event) => setForm({ ...form, address: event.target.value })} /></label>
              <label>Payment terms<input value={form.payment_terms ?? ""} onChange={(event) => setForm({ ...form, payment_terms: event.target.value })} /></label>
              <label>Lead time days<input min="0" type="number" value={form.lead_time_days} onChange={(event) => setForm({ ...form, lead_time_days: Number(event.target.value) })} /></label>
              <label className="checkbox-row"><input checked={form.is_active} onChange={(event) => setForm({ ...form, is_active: event.target.checked })} type="checkbox" /> Active supplier</label>
              <FormButtons editing={Boolean(editingId)} onCancel={resetForm} saving={saving} />
            </form>
          ) : null}
        </aside>
      </section>
    </section>
  );
}

function CategoriesPage() {
  const { token, user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [categories, setCategories] = useState<Category[]>([]);
  const [form, setForm] = useState<CategoryPayload>(emptyCategoryForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      setCategories(await listCategories(token, search));
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, [search, token]);

  useEffect(() => {
    void load();
  }, [load]);

  const resetForm = () => {
    setEditingId(null);
    setForm(emptyCategoryForm);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token || !isAdmin) return;
    setSaving(true);
    setError(null);
    const payload = { name: form.name.trim(), description: cleanOptional(form.description) };
    try {
      if (editingId) {
        await updateCategory(token, editingId, payload);
      } else {
        await createCategory(token, payload);
      }
      resetForm();
      await load();
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setSaving(false);
    }
  };

  return (
    <SimpleMasterPage
      canEdit={Boolean(isAdmin)}
      description="Manage product grouping for filtering, dashboards, sales summaries, and inventory health reporting."
      error={error}
      formTitle={editingId ? "Edit category" : "Create category"}
      loading={loading}
      metricLabel="Categories"
      onRefresh={load}
      search={search}
      setSearch={setSearch}
      title="Category management"
    >
      <article className="panel wide">
        <PanelTitle title="Categories" />
        {loading ? <LoadingState label="Loading categories" /> : null}
        {!loading && categories.length === 0 ? <EmptyState title="No categories found" message="Create categories before adding products." /> : null}
        {!loading && categories.length > 0 ? (
          <div className="table-shell"><table><thead><tr><th>Name</th><th>Description</th><th>Actions</th></tr></thead><tbody>
            {categories.map((category) => (
              <tr key={category.id}><td>{category.name}</td><td>{category.description ?? "Not set"}</td><td><div className="table-actions"><button disabled={!isAdmin} onClick={() => { setEditingId(category.id); setForm({ name: category.name, description: category.description ?? "" }); }} type="button"><Edit3 aria-hidden="true" size={14} />Edit</button></div></td></tr>
            ))}
          </tbody></table></div>
        ) : null}
      </article>
      <aside className="panel">
        <AdminGate isAdmin={Boolean(isAdmin)} />
        {isAdmin ? (
          <form className="master-form" onSubmit={handleSubmit}>
            <PanelTitle title={editingId ? "Edit category" : "Create category"} />
            <label>Name<input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
            <label>Description<textarea value={form.description ?? ""} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label>
            <FormButtons editing={Boolean(editingId)} onCancel={resetForm} saving={saving} />
          </form>
        ) : null}
      </aside>
    </SimpleMasterPage>
  );
}

function BranchesPage() {
  const { token, user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [branches, setBranches] = useState<Branch[]>([]);
  const [form, setForm] = useState<BranchPayload>(emptyBranchForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      setBranches(await listBranches(token, { search, includeInactive }));
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, [includeInactive, search, token]);

  useEffect(() => {
    void load();
  }, [load]);

  const resetForm = () => {
    setEditingId(null);
    setForm(emptyBranchForm);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token || !isAdmin) return;
    setSaving(true);
    setError(null);
    const payload: BranchPayload = {
      ...form,
      name: form.name.trim(),
      address: cleanOptional(form.address),
      city: cleanOptional(form.city),
      manager_name: cleanOptional(form.manager_name),
    };
    try {
      if (editingId) {
        await updateBranch(token, editingId, payload);
      } else {
        await createBranch(token, payload);
      }
      resetForm();
      await load();
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="page-stack">
      <MasterHeader description="Configure store branches for inventory, sales, purchase orders, and role branch scope." title="Branch management" />
      <PageToolbar includeInactive={includeInactive} onRefresh={load} search={search} setIncludeInactive={setIncludeInactive} setSearch={setSearch} />
      <section className="metric-grid">
        <MetricCard metric={{ label: "Branches Loaded", value: String(branches.length), detail: "Current filter result", tone: "blue" }} />
        <MetricCard metric={{ label: "Active Branches", value: String(branches.filter((branch) => branch.is_active).length), detail: "Operational locations", tone: "green" }} />
        <MetricCard metric={{ label: "Access", value: "Admin only", detail: "Backend enforced writes", tone: "amber" }} />
        <MetricCard metric={{ label: "Scope", value: "Branch based", detail: "Used by managers and staff", tone: "slate" }} />
      </section>
      {error ? <ErrorState message={error} title="Branch action failed" /> : null}
      <section className="master-grid">
        <article className="panel wide">
          <PanelTitle title="Branches" />
          {loading ? <LoadingState label="Loading branches" /> : null}
          {!loading && branches.length === 0 ? <EmptyState title="No branches found" message="Create a branch to scope inventory and staff users." /> : null}
          {!loading && branches.length > 0 ? (
            <div className="table-shell"><table><thead><tr><th>Name</th><th>City</th><th>Manager</th><th>Status</th><th>Actions</th></tr></thead><tbody>
              {branches.map((branch) => (
                <tr key={branch.id}><td>{branch.name}</td><td>{branch.city ?? "Not set"}</td><td>{branch.manager_name ?? "Not set"}</td><td>{branch.is_active ? "Active" : "Inactive"}</td><td><div className="table-actions"><button disabled={!isAdmin} onClick={() => { setEditingId(branch.id); setForm({ name: branch.name, address: branch.address ?? "", city: branch.city ?? "", manager_name: branch.manager_name ?? "", is_active: branch.is_active }); }} type="button"><Edit3 aria-hidden="true" size={14} />Edit</button></div></td></tr>
              ))}
            </tbody></table></div>
          ) : null}
        </article>
        <aside className="panel">
          <AdminGate isAdmin={Boolean(isAdmin)} />
          {isAdmin ? (
            <form className="master-form" onSubmit={handleSubmit}>
              <PanelTitle title={editingId ? "Edit branch" : "Create branch"} />
              <label>Name<input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
              <label>Address<input value={form.address ?? ""} onChange={(event) => setForm({ ...form, address: event.target.value })} /></label>
              <label>City<input value={form.city ?? ""} onChange={(event) => setForm({ ...form, city: event.target.value })} /></label>
              <label>Manager<input value={form.manager_name ?? ""} onChange={(event) => setForm({ ...form, manager_name: event.target.value })} /></label>
              <label className="checkbox-row"><input checked={form.is_active} onChange={(event) => setForm({ ...form, is_active: event.target.checked })} type="checkbox" /> Active branch</label>
              <FormButtons editing={Boolean(editingId)} onCancel={resetForm} saving={saving} />
            </form>
          ) : null}
        </aside>
      </section>
    </section>
  );
}

function MasterHeader({ title, description }: { title: string; description: string }) {
  return (
    <div className="page-header">
      <div>
        <p className="eyebrow">Master data</p>
        <h2>{title}</h2>
        <p className="page-description">{description}</p>
      </div>
      <div className="page-header-side">
        <span className="role-scope">Admin writes only</span>
      </div>
    </div>
  );
}

function PanelTitle({ title }: { title: string }) {
  return (
    <div className="panel-header">
      <div>
        <p className="eyebrow">Reference data</p>
        <h3>{title}</h3>
      </div>
    </div>
  );
}

function FormButtons({
  editing,
  onCancel,
  saving,
}: {
  editing: boolean;
  onCancel: () => void;
  saving: boolean;
}) {
  return (
    <div className="form-actions">
      <button className="action-button primary" disabled={saving} type="submit">
        <Plus aria-hidden="true" size={16} />
        {saving ? "Saving" : editing ? "Save changes" : "Create"}
      </button>
      {editing ? (
        <button className="action-button secondary" onClick={onCancel} type="button">
          Cancel
        </button>
      ) : null}
    </div>
  );
}

function SimpleMasterPage({
  children,
  description,
  error,
  loading,
  metricLabel,
  onRefresh,
  search,
  setSearch,
  title,
}: {
  children: ReactNode;
  canEdit: boolean;
  description: string;
  error: string | null;
  formTitle: string;
  loading: boolean;
  metricLabel: string;
  onRefresh: () => void;
  search: string;
  setSearch: (value: string) => void;
  title: string;
}) {
  const [includeInactive, setIncludeInactive] = useState(false);

  return (
    <section className="page-stack">
      <MasterHeader description={description} title={title} />
      <PageToolbar
        includeInactive={includeInactive}
        onRefresh={onRefresh}
        search={search}
        setIncludeInactive={setIncludeInactive}
        setSearch={setSearch}
        showInactiveToggle={false}
      />
      <section className="metric-grid">
        <MetricCard metric={{ label: metricLabel, value: loading ? "Loading" : "Ready", detail: "Search-aware list", tone: "blue" }} />
        <MetricCard metric={{ label: "Permission", value: "Admin writes", detail: "Backend enforced", tone: "amber" }} />
        <MetricCard metric={{ label: "Audit", value: "Enabled", detail: "Create and update actions", tone: "green" }} />
        <MetricCard metric={{ label: "UI State", value: "Connected", detail: "Loading and error handling", tone: "slate" }} />
      </section>
      {error ? <ErrorState message={error} title={`${title} action failed`} /> : null}
      <section className="master-grid">{children}</section>
    </section>
  );
}
