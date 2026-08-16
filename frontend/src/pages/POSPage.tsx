import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CreditCard, Plus, ReceiptText, RotateCw, Search, Send, Trash2 } from "lucide-react";

import { listPaymentModes, getBusinessProfile } from "../api/businessSettings";
import { ApiError } from "../api/client";
import { createCustomer, listCustomers } from "../api/customers";
import { listBranches } from "../api/masterData";
import { checkoutPosInvoice, holdDraftInvoice, quotePosInvoice, searchPosProducts } from "../api/pos";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, ErrorState, LoadingState, MetricCard } from "../components/ui";
import type {
  Branch,
  BusinessProfile,
  Customer,
  CustomerPayload,
  Invoice,
  InvoiceQuote,
  InvoiceType,
  PaymentMode,
  POSCheckoutPayload,
  POSPaymentPayload,
  POSProductSearchResult,
  POSQuotePayload,
} from "../types";
import { formatCurrency, formatQuantity, formatStatus } from "../utils/format";

type CartLine = {
  product: POSProductSearchResult;
  quantity: string;
  discount: string;
  unitPrice: string;
};

type PaymentRow = {
  id: string;
  paymentModeId: number;
  amount: string;
  referenceNumber: string;
  notes: string;
};

const quickCustomerDefaults: CustomerPayload = {
  name: "",
  phone: "",
  email: "",
  gstin: "",
  billing_address: "",
  shipping_address: "",
  city: "",
  state: "",
  state_code: "",
  pincode: "",
  branch_id: null,
  company_id: null,
  credit_limit: "0.00",
  opening_balance: "0.00",
  is_active: true,
};

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "Could not complete the POS request. Check that the backend is running.";
}

function cleanOptional(value: string | null | undefined): string | null {
  const trimmed = (value ?? "").trim();
  return trimmed ? trimmed : null;
}

function asMoneyInput(value: string | number): string {
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) {
    return "0.00";
  }
  return numberValue.toFixed(2);
}

function paymentRow(paymentModeId = 0, amount = "0.00"): PaymentRow {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    paymentModeId,
    amount,
    referenceNumber: "",
    notes: "",
  };
}

function invoiceTypeLabel(value: InvoiceType): string {
  return value === "gst" ? "GST" : "Non-GST";
}

export function POSPage() {
  const { token, user } = useAuth();
  const searchRef = useRef<HTMLInputElement | null>(null);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [paymentModes, setPaymentModes] = useState<PaymentMode[]>([]);
  const [businessProfile, setBusinessProfile] = useState<BusinessProfile | null>(null);
  const [branchId, setBranchId] = useState(0);
  const [customerId, setCustomerId] = useState(0);
  const [invoiceType, setInvoiceType] = useState<InvoiceType>("gst");
  const [placeState, setPlaceState] = useState("");
  const [placeStateCode, setPlaceStateCode] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [searchResults, setSearchResults] = useState<POSProductSearchResult[]>([]);
  const [cart, setCart] = useState<CartLine[]>([]);
  const [payments, setPayments] = useState<PaymentRow[]>([]);
  const [quote, setQuote] = useState<InvoiceQuote | null>(null);
  const [lastInvoice, setLastInvoice] = useState<Invoice | null>(null);
  const [quickCustomerOpen, setQuickCustomerOpen] = useState(false);
  const [quickCustomer, setQuickCustomer] = useState<CustomerPayload>(quickCustomerDefaults);
  const [loading, setLoading] = useState(true);
  const [customersLoading, setCustomersLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [quoting, setQuoting] = useState(false);
  const [checkingOut, setCheckingOut] = useState(false);
  const [holding, setHolding] = useState(false);
  const [savingCustomer, setSavingCustomer] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [quoteError, setQuoteError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const canUsePOS = user?.role === "admin" || user?.role === "store_manager" || user?.role === "staff";
  const canQuickCreateCustomer = user?.role === "admin" || user?.role === "store_manager";
  const branchLocked = user?.role === "store_manager" || user?.role === "staff";

  const selectedCustomer = useMemo(
    () => customers.find((customer) => customer.id === customerId) ?? null,
    [customerId, customers],
  );

  const selectedBranch = useMemo(
    () => branches.find((branch) => branch.id === branchId) ?? null,
    [branchId, branches],
  );

  const activePaymentModes = useMemo(
    () => paymentModes.filter((mode) => mode.is_active && mode.mode_type !== "credit"),
    [paymentModes],
  );

  const cashMode = useMemo(
    () => activePaymentModes.find((mode) => mode.mode_type === "cash") ?? activePaymentModes[0],
    [activePaymentModes],
  );

  const paymentTotal = useMemo(
    () => payments.reduce((total, row) => total + (Number(row.amount) || 0), 0),
    [payments],
  );

  const quoteByProductId = useMemo(() => {
    const map = new Map<number, InvoiceQuote["items"][number]>();
    quote?.items.forEach((item) => map.set(item.product_id, item));
    return map;
  }, [quote]);

  const placeOptions = useMemo(() => {
    const options = new Map<string, { state: string; stateCode: string }>();
    if (businessProfile?.state_code) {
      options.set(businessProfile.state_code, {
        state: businessProfile.state ?? "Business state",
        stateCode: businessProfile.state_code,
      });
    }
    customers.forEach((customer) => {
      if (customer.state_code) {
        options.set(customer.state_code, {
          state: customer.state ?? customer.branch_name ?? "Customer state",
          stateCode: customer.state_code,
        });
      }
    });
    return Array.from(options.values());
  }, [businessProfile, customers]);

  const metrics = useMemo(
    () => [
      {
        label: "Cart Lines",
        value: String(cart.length),
        detail: branchId ? selectedBranch?.name ?? "Selected branch" : "Select branch",
        tone: "blue" as const,
      },
      {
        label: "Backend Total",
        value: quote ? formatCurrency(quote.grand_total) : "Not quoted",
        detail: quote ? `${invoiceTypeLabel(quote.invoice_type)} backend quote` : "Add items to quote",
        tone: "green" as const,
      },
      {
        label: "Tax Total",
        value: quote
          ? formatCurrency(
              Number(quote.cgst_total) + Number(quote.sgst_total) + Number(quote.igst_total) + Number(quote.cess_total),
            )
          : formatCurrency(0),
        detail: quote ? "Stored tax rows after checkout" : "Awaiting quote",
        tone: "amber" as const,
      },
      {
        label: "Balance",
        value: quote ? formatCurrency(Math.max(Number(quote.grand_total) - paymentTotal, 0)) : formatCurrency(0),
        detail: selectedCustomer ? "Customer credit allowed" : "Walk-in must be paid",
        tone: selectedCustomer ? "slate" as const : "rose" as const,
      },
    ],
    [branchId, cart.length, invoiceType, paymentTotal, quote, selectedBranch?.name, selectedCustomer],
  );

  const buildQuotePayload = useCallback((): POSQuotePayload | null => {
    if (!branchId || cart.length === 0) {
      return null;
    }
    return {
      branch_id: branchId,
      customer_id: customerId || null,
      invoice_type: invoiceType,
      place_of_supply_state: cleanOptional(placeState),
      place_of_supply_state_code: cleanOptional(placeStateCode)?.toUpperCase() ?? null,
      invoice_date: new Date().toISOString(),
      items: cart.map((line) => ({
        product_id: line.product.product_id,
        quantity: line.quantity || "1.00",
        unit_price: line.unitPrice || line.product.selling_price,
        discount: line.discount || "0.00",
      })),
    };
  }, [branchId, cart, customerId, invoiceType, placeState, placeStateCode]);

  const loadInitial = useCallback(async () => {
    if (!token || !user) return;
    setLoading(true);
    setError(null);
    try {
      const [branchRows, modes, profile] = await Promise.all([
        listBranches(token, { includeInactive: false }),
        listPaymentModes(token, false),
        getBusinessProfile(token),
      ]);
      setBranches(branchRows);
      setPaymentModes(modes);
      setBusinessProfile(profile);
      const defaultBranchId = user.role === "admin" ? branchRows[0]?.id ?? 0 : user.branch_id ?? branchRows[0]?.id ?? 0;
      setBranchId(defaultBranchId);
      setPlaceState(profile.state ?? "");
      setPlaceStateCode(profile.state_code ?? "");
      const defaultMode = modes.find((mode) => mode.is_active && mode.mode_type === "cash") ?? modes.find((mode) => mode.is_active);
      setPayments(defaultMode ? [paymentRow(defaultMode.id)] : []);
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, [token, user]);

  const loadCustomers = useCallback(async () => {
    if (!token || !branchId) {
      setCustomers([]);
      return;
    }
    setCustomersLoading(true);
    try {
      setCustomers(await listCustomers(token, { branchId, limit: 250 }));
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setCustomersLoading(false);
    }
  }, [branchId, token]);

  useEffect(() => {
    void loadInitial();
  }, [loadInitial]);

  useEffect(() => {
    void loadCustomers();
  }, [loadCustomers]);

  useEffect(() => {
    searchRef.current?.focus();
  }, []);

  useEffect(() => {
    if (selectedCustomer) {
      setPlaceState(selectedCustomer.state ?? businessProfile?.state ?? "");
      setPlaceStateCode(selectedCustomer.state_code ?? businessProfile?.state_code ?? "");
    } else if (businessProfile) {
      setPlaceState(businessProfile.state ?? "");
      setPlaceStateCode(businessProfile.state_code ?? "");
    }
  }, [businessProfile, selectedCustomer]);

  useEffect(() => {
    if (customerId && !customers.some((customer) => customer.id === customerId)) {
      setCustomerId(0);
    }
  }, [customerId, customers]);

  useEffect(() => {
    const payload = buildQuotePayload();
    if (!token || !payload) {
      setQuote(null);
      setQuoteError(null);
      return;
    }

    const timeoutId = window.setTimeout(() => {
      setQuoting(true);
      setQuoteError(null);
      quotePosInvoice(token, payload)
        .then(setQuote)
        .catch((quoteFailure) => {
          setQuote(null);
          setQuoteError(errorMessage(quoteFailure));
        })
        .finally(() => setQuoting(false));
    }, 250);

    return () => window.clearTimeout(timeoutId);
  }, [buildQuotePayload, token]);

  const addProductToCart = (product: POSProductSearchResult) => {
    setCart((current) => {
      const existing = current.find((line) => line.product.product_id === product.product_id);
      if (existing) {
        return current.map((line) =>
          line.product.product_id === product.product_id
            ? { ...line, quantity: asMoneyInput((Number(line.quantity) || 0) + 1) }
            : line,
        );
      }
      return [
        ...current,
        {
          product,
          quantity: "1.00",
          discount: "0.00",
          unitPrice: product.selling_price,
        },
      ];
    });
    setSearchTerm("");
    setSearchResults([]);
    setLastInvoice(null);
    window.setTimeout(() => searchRef.current?.focus(), 0);
  };

  const runProductSearch = async () => {
    if (!token || !branchId || !searchTerm.trim()) {
      return;
    }
    setSearching(true);
    setError(null);
    setSuccess(null);
    setLastInvoice(null);
    try {
      const rows = await searchPosProducts(token, searchTerm.trim(), { branchId, limit: 12 });
      setSearchResults(rows);
      const exact = rows.find(
        (row) =>
          row.primary_barcode === searchTerm.trim() ||
          row.sku.toLowerCase() === searchTerm.trim().toLowerCase(),
      );
      if (rows.length === 1 || exact) {
        addProductToCart(exact ?? rows[0]);
      } else if (rows.length === 0) {
        setQuoteError(`No product found for "${searchTerm.trim()}".`);
      }
    } catch (searchError) {
      setError(errorMessage(searchError));
    } finally {
      setSearching(false);
    }
  };

  const submitSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void runProductSearch();
  };

  const updateCartLine = (productId: number, changes: Partial<CartLine>) => {
    setCart((current) =>
      current.map((line) => (line.product.product_id === productId ? { ...line, ...changes } : line)),
    );
  };

  const removeCartLine = (productId: number) => {
    setCart((current) => current.filter((line) => line.product.product_id !== productId));
  };

  const addPaymentRow = () => {
    setPayments((current) => [...current, paymentRow(cashMode?.id ?? activePaymentModes[0]?.id ?? 0)]);
  };

  const updatePaymentRow = (id: string, changes: Partial<PaymentRow>) => {
    setPayments((current) => current.map((row) => (row.id === id ? { ...row, ...changes } : row)));
  };

  const removePaymentRow = (id: string) => {
    setPayments((current) => (current.length === 1 ? current : current.filter((row) => row.id !== id)));
  };

  const buildCheckoutPayload = (paymentPayloads: POSPaymentPayload[]): POSCheckoutPayload | null => {
    const quotePayload = buildQuotePayload();
    if (!quotePayload) {
      return null;
    }
    return {
      ...quotePayload,
      payments: paymentPayloads,
    };
  };

  const resetAfterInvoice = (invoice: Invoice) => {
    setLastInvoice(invoice);
    setSuccess(`Invoice ${invoice.invoice_number} completed. Backend total ${formatCurrency(invoice.grand_total)}.`);
    setCart([]);
    setSearchResults([]);
    setSearchTerm("");
    setQuote(null);
    if (cashMode) {
      setPayments([paymentRow(cashMode.id)]);
    }
    window.setTimeout(() => searchRef.current?.focus(), 0);
  };

  const checkoutWithPayments = async (paymentPayloads: POSPaymentPayload[]) => {
    if (!token) return;
    const payload = buildCheckoutPayload(paymentPayloads);
    if (!payload) {
      setError("Add at least one product before checkout.");
      return;
    }
    setCheckingOut(true);
    setError(null);
    setQuoteError(null);
    setSuccess(null);
    try {
      const invoice = await checkoutPosInvoice(token, payload);
      resetAfterInvoice(invoice);
    } catch (checkoutError) {
      setError(errorMessage(checkoutError));
    } finally {
      setCheckingOut(false);
    }
  };

  const submitCheckout = async () => {
    const paymentPayloads = payments
      .filter((row) => Number(row.amount) > 0)
      .map((row) => ({
        payment_mode_id: row.paymentModeId || null,
        amount: row.amount,
        reference_number: cleanOptional(row.referenceNumber),
        notes: cleanOptional(row.notes),
      }));
    await checkoutWithPayments(paymentPayloads);
  };

  const cashCheckout = async () => {
    if (!quote || !cashMode) {
      setError("Cash payment mode or backend quote is not available.");
      return;
    }
    await checkoutWithPayments([
      {
        payment_mode_id: cashMode.id,
        amount: quote.grand_total,
        reference_number: null,
        notes: "One-click cash checkout",
      },
    ]);
  };

  const creditCheckout = async () => {
    if (!selectedCustomer) {
      setError("Select a customer before creating a credit invoice.");
      return;
    }
    await checkoutWithPayments([]);
  };

  const holdDraft = async () => {
    if (!token) return;
    const payload = buildQuotePayload();
    if (!payload) {
      setError("Add items before holding an invoice draft.");
      return;
    }
    setHolding(true);
    setError(null);
    setSuccess(null);
    try {
      const invoice = await holdDraftInvoice(token, payload);
      setLastInvoice(invoice);
      setSuccess(`Draft ${invoice.invoice_number} held. Stock was not reduced.`);
      setCart([]);
      setQuote(null);
    } catch (holdError) {
      setError(errorMessage(holdError));
    } finally {
      setHolding(false);
    }
  };

  const submitQuickCustomer = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token || !canQuickCreateCustomer) return;
    setSavingCustomer(true);
    setError(null);
    try {
      const payload: CustomerPayload = {
        ...quickCustomer,
        name: quickCustomer.name.trim(),
        phone: cleanOptional(quickCustomer.phone),
        email: cleanOptional(quickCustomer.email),
        gstin: cleanOptional(quickCustomer.gstin)?.toUpperCase() ?? null,
        billing_address: cleanOptional(quickCustomer.billing_address),
        shipping_address: cleanOptional(quickCustomer.shipping_address),
        city: cleanOptional(quickCustomer.city),
        state: cleanOptional(quickCustomer.state || businessProfile?.state),
        state_code: cleanOptional(quickCustomer.state_code || businessProfile?.state_code)?.toUpperCase() ?? null,
        pincode: cleanOptional(quickCustomer.pincode),
        branch_id: branchId || null,
        company_id: null,
        credit_limit: quickCustomer.credit_limit || "0.00",
        opening_balance: "0.00",
        is_active: true,
      };
      const customer = await createCustomer(token, payload);
      setCustomers((current) => [...current, customer].sort((left, right) => left.name.localeCompare(right.name)));
      setCustomerId(customer.id);
      setQuickCustomer(quickCustomerDefaults);
      setQuickCustomerOpen(false);
      setSuccess(`${customer.name} added to this invoice.`);
    } catch (customerError) {
      setError(errorMessage(customerError));
    } finally {
      setSavingCustomer(false);
    }
  };

  if (loading) {
    return <LoadingState label="Loading POS workspace" />;
  }

  if (!canUsePOS) {
    return <ErrorState title="POS access blocked" message="This role cannot issue sales or POS invoices." />;
  }

  return (
    <section className="page-stack">
      <div className="page-header">
        <div>
          <p className="eyebrow">Counter billing</p>
          <h2>POS Billing</h2>
          <p className="page-description">
            Barcode-first invoice checkout with backend-calculated GST, stock reduction, payment rows, and customer credit handling.
          </p>
        </div>
        <div className="page-header-side">
          <span className="role-scope">POS enabled</span>
          <button className="action-button secondary" onClick={() => void loadInitial()} type="button">
            <RotateCw aria-hidden="true" size={16} />
            Refresh setup
          </button>
        </div>
      </div>

      <section className="metric-grid">
        {metrics.map((metric) => (
          <MetricCard key={metric.label} metric={metric} />
        ))}
      </section>

      {error ? <ErrorState message={error} title="POS action failed" /> : null}
      {quoteError ? <ErrorState message={quoteError} title="Quote blocked" /> : null}
      {success ? <div className="success-banner">{success}</div> : null}

      {lastInvoice ? (
        <article className="panel pos-success-panel">
          <div>
            <p className="eyebrow">Invoice</p>
            <h3>{lastInvoice.invoice_number}</h3>
          </div>
          <div className="pos-success-grid">
            <span>{formatStatus(lastInvoice.status)}</span>
            <strong>{formatCurrency(lastInvoice.grand_total)}</strong>
            <span>Paid {formatCurrency(lastInvoice.paid_amount)}</span>
            <span>Due {formatCurrency(lastInvoice.balance_due)}</span>
          </div>
          <div className="sale-button-row">
            <button className="action-button secondary" disabled type="button">
              Print in Phase 6
            </button>
            <button className="action-button secondary" disabled type="button">
              PDF in Phase 6
            </button>
          </div>
        </article>
      ) : null}

      <section className="pos-grid">
        <article className="panel pos-main-panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Scan or search</p>
              <h3>Product lookup</h3>
            </div>
            <ReceiptText aria-hidden="true" size={19} />
          </div>

          <div className="pos-controls">
            <label>
              Branch
              <select
                disabled={branchLocked}
                onChange={(event) => setBranchId(Number(event.target.value))}
                value={branchId}
              >
                <option value={0}>Select branch</option>
                {branches.map((branch) => (
                  <option key={branch.id} value={branch.id}>
                    {branch.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Invoice type
              <select onChange={(event) => setInvoiceType(event.target.value as InvoiceType)} value={invoiceType}>
                <option value="gst">GST</option>
                <option value="non_gst">Non-GST</option>
              </select>
            </label>
            <label>
              Place of supply
              <select
                onChange={(event) => {
                  const option = placeOptions.find((row) => row.stateCode === event.target.value);
                  setPlaceState(option?.state ?? "");
                  setPlaceStateCode(option?.stateCode ?? "");
                }}
                value={placeStateCode}
              >
                <option value="">Manual</option>
                {placeOptions.map((option) => (
                  <option key={option.stateCode} value={option.stateCode}>
                    {option.state} ({option.stateCode})
                  </option>
                ))}
              </select>
            </label>
            <label>
              State code
              <input
                maxLength={2}
                onChange={(event) => setPlaceStateCode(event.target.value.toUpperCase())}
                value={placeStateCode}
              />
            </label>
          </div>

          <form className="pos-search-row" onSubmit={submitSearch}>
            <div className="search-shell pos-search-shell">
              <Search aria-hidden="true" size={17} />
              <input
                aria-label="Barcode, SKU, or product name"
                disabled={!branchId}
                onChange={(event) => setSearchTerm(event.target.value)}
                placeholder="Scan barcode or type SKU/name"
                ref={searchRef}
                type="search"
                value={searchTerm}
              />
            </div>
            <button className="action-button primary" disabled={!branchId || searching} type="submit">
              <Plus aria-hidden="true" size={16} />
              {searching ? "Searching" : "Add"}
            </button>
          </form>

          {searchResults.length > 1 ? (
            <div className="pos-search-results">
              {searchResults.map((product) => (
                <button key={product.product_id} onClick={() => addProductToCart(product)} type="button">
                  <strong>{product.name}</strong>
                  <span>{product.sku} {product.primary_barcode ? `| ${product.primary_barcode}` : ""}</span>
                  <b>{formatCurrency(product.selling_price)} | {formatQuantity(product.quantity_on_hand)} in stock</b>
                </button>
              ))}
            </div>
          ) : null}

          <div className="panel-header compact-heading">
            <div>
              <p className="eyebrow">Cart</p>
              <h3>Invoice lines</h3>
            </div>
            {quoting ? <span className="role-scope">Quoting</span> : null}
          </div>

          {cart.length === 0 ? (
            <EmptyState title="Cart is empty" message="Scan a barcode or search by SKU/name to add products." />
          ) : (
            <div className="table-shell pos-cart-table">
              <table>
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>HSN</th>
                    <th>GST</th>
                    <th>MRP</th>
                    <th>Unit Price</th>
                    <th>Qty</th>
                    <th>Discount</th>
                    <th>Taxable</th>
                    <th>Tax</th>
                    <th>Total</th>
                    <th>Stock</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {cart.map((line) => {
                    const quotedLine = quoteByProductId.get(line.product.product_id);
                    const taxTotal = quotedLine
                      ? Number(quotedLine.cgst_total) +
                        Number(quotedLine.sgst_total) +
                        Number(quotedLine.igst_total) +
                        Number(quotedLine.cess_total)
                      : 0;
                    const stockAvailable = quotedLine?.quantity_on_hand ?? line.product.quantity_on_hand;
                    const isInsufficient = Number(line.quantity) > Number(stockAvailable);
                    return (
                      <tr className={isInsufficient ? "stock-warning-row" : ""} key={line.product.product_id}>
                        <td>
                          <strong>{line.product.name}</strong>
                          <span>{line.product.sku} {line.product.primary_barcode ? `| ${line.product.primary_barcode}` : ""}</span>
                        </td>
                        <td>{line.product.hsn_sac_code ?? "Not set"}</td>
                        <td>{quotedLine ? `${quotedLine.gst_rate}%` : `${line.product.gst_rate}%`}</td>
                        <td>{line.product.mrp ? formatCurrency(line.product.mrp) : "Not set"}</td>
                        <td>
                          <input
                            aria-label={`Unit price for ${line.product.name}`}
                            inputMode="decimal"
                            onChange={(event) => updateCartLine(line.product.product_id, { unitPrice: event.target.value })}
                            value={line.unitPrice}
                          />
                        </td>
                        <td>
                          <input
                            aria-label={`Quantity for ${line.product.name}`}
                            inputMode="decimal"
                            onChange={(event) => updateCartLine(line.product.product_id, { quantity: event.target.value })}
                            value={line.quantity}
                          />
                        </td>
                        <td>
                          <input
                            aria-label={`Discount for ${line.product.name}`}
                            inputMode="decimal"
                            onChange={(event) => updateCartLine(line.product.product_id, { discount: event.target.value })}
                            value={line.discount}
                          />
                        </td>
                        <td>{quotedLine ? formatCurrency(quotedLine.taxable_value) : "Quote"}</td>
                        <td>{quotedLine ? formatCurrency(taxTotal) : "Quote"}</td>
                        <td>{quotedLine ? formatCurrency(quotedLine.line_total) : "Quote"}</td>
                        <td>
                          <span className={isInsufficient ? "status-badge warning" : "status-badge ok"}>
                            {formatQuantity(stockAvailable)}
                          </span>
                        </td>
                        <td>
                          <button
                            aria-label={`Remove ${line.product.name}`}
                            className="icon-button"
                            onClick={() => removeCartLine(line.product.product_id)}
                            type="button"
                          >
                            <Trash2 aria-hidden="true" size={16} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </article>

        <aside className="panel pos-side-panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Customer</p>
              <h3>Billing account</h3>
            </div>
          </div>
          <label className="pos-field">
            Customer
            <select
              disabled={customersLoading}
              onChange={(event) => setCustomerId(Number(event.target.value))}
              value={customerId}
            >
              <option value={0}>Walk-in customer</option>
              {customers.map((customer) => (
                <option key={customer.id} value={customer.id}>
                  {customer.name} {customer.phone ? `(${customer.phone})` : ""}
                </option>
              ))}
            </select>
          </label>
          {selectedCustomer ? (
            <div className="detail-list pos-customer-detail">
              <div><span>Outstanding</span><strong>{formatCurrency(selectedCustomer.outstanding_balance)}</strong></div>
              <div><span>Available credit</span><strong>{formatCurrency(selectedCustomer.available_credit)}</strong></div>
              <div><span>GSTIN</span><strong>{selectedCustomer.gstin ?? "B2C"}</strong></div>
            </div>
          ) : null}

          {canQuickCreateCustomer ? (
            <>
              <button
                className="action-button secondary full-width"
                onClick={() => setQuickCustomerOpen((open) => !open)}
                type="button"
              >
                <Plus aria-hidden="true" size={16} />
                Quick customer
              </button>
              {quickCustomerOpen ? (
                <form className="master-form quick-customer-form" onSubmit={submitQuickCustomer}>
                  <label>Name<input required value={quickCustomer.name} onChange={(event) => setQuickCustomer({ ...quickCustomer, name: event.target.value })} /></label>
                  <div className="form-grid two">
                    <label>Phone<input value={quickCustomer.phone ?? ""} onChange={(event) => setQuickCustomer({ ...quickCustomer, phone: event.target.value })} /></label>
                    <label>GSTIN<input value={quickCustomer.gstin ?? ""} onChange={(event) => setQuickCustomer({ ...quickCustomer, gstin: event.target.value })} /></label>
                    <label>State<input value={quickCustomer.state ?? businessProfile?.state ?? ""} onChange={(event) => setQuickCustomer({ ...quickCustomer, state: event.target.value })} /></label>
                    <label>Code<input maxLength={2} value={quickCustomer.state_code ?? businessProfile?.state_code ?? ""} onChange={(event) => setQuickCustomer({ ...quickCustomer, state_code: event.target.value })} /></label>
                    <label>Credit limit<input min="0" step="0.01" type="number" value={quickCustomer.credit_limit} onChange={(event) => setQuickCustomer({ ...quickCustomer, credit_limit: event.target.value })} /></label>
                  </div>
                  <label>Billing address<textarea value={quickCustomer.billing_address ?? ""} onChange={(event) => setQuickCustomer({ ...quickCustomer, billing_address: event.target.value })} /></label>
                  <button className="action-button primary" disabled={savingCustomer} type="submit">
                    {savingCustomer ? "Saving" : "Add customer"}
                  </button>
                </form>
              ) : null}
            </>
          ) : null}

          <div className="panel-header compact-heading pos-payment-heading">
            <div>
              <p className="eyebrow">Payment</p>
              <h3>Collection</h3>
            </div>
            <CreditCard aria-hidden="true" size={18} />
          </div>
          <div className="payment-list">
            {payments.map((row) => (
              <div className="payment-row" key={row.id}>
                <select
                  aria-label="Payment mode"
                  onChange={(event) => updatePaymentRow(row.id, { paymentModeId: Number(event.target.value) })}
                  value={row.paymentModeId}
                >
                  <option value={0}>Mode</option>
                  {activePaymentModes.map((mode) => (
                    <option key={mode.id} value={mode.id}>{mode.name}</option>
                  ))}
                </select>
                <input
                  aria-label="Payment amount"
                  inputMode="decimal"
                  onChange={(event) => updatePaymentRow(row.id, { amount: event.target.value })}
                  value={row.amount}
                />
                <input
                  aria-label="Payment reference"
                  onChange={(event) => updatePaymentRow(row.id, { referenceNumber: event.target.value })}
                  placeholder="Ref"
                  value={row.referenceNumber}
                />
                <button
                  aria-label="Remove payment row"
                  className="icon-button"
                  disabled={payments.length === 1}
                  onClick={() => removePaymentRow(row.id)}
                  type="button"
                >
                  <Trash2 aria-hidden="true" size={15} />
                </button>
              </div>
            ))}
          </div>
          <button className="action-button secondary full-width" onClick={addPaymentRow} type="button">
            <Plus aria-hidden="true" size={16} />
            Split payment
          </button>

          <div className="pos-total-panel">
            <div><span>Subtotal</span><strong>{quote ? formatCurrency(quote.subtotal) : formatCurrency(0)}</strong></div>
            <div><span>Discount</span><strong>{quote ? formatCurrency(quote.discount_total) : formatCurrency(0)}</strong></div>
            <div><span>Taxable</span><strong>{quote ? formatCurrency(quote.taxable_total) : formatCurrency(0)}</strong></div>
            <div><span>CGST</span><strong>{quote ? formatCurrency(quote.cgst_total) : formatCurrency(0)}</strong></div>
            <div><span>SGST</span><strong>{quote ? formatCurrency(quote.sgst_total) : formatCurrency(0)}</strong></div>
            <div><span>IGST</span><strong>{quote ? formatCurrency(quote.igst_total) : formatCurrency(0)}</strong></div>
            <div className="grand"><span>Total</span><strong>{quote ? formatCurrency(quote.grand_total) : formatCurrency(0)}</strong></div>
            <div><span>Entered payment</span><strong>{formatCurrency(paymentTotal)}</strong></div>
          </div>

          <div className="pos-actions">
            <button className="action-button primary full-width" disabled={!quote || checkingOut || Boolean(quoteError)} onClick={cashCheckout} type="button">
              <Send aria-hidden="true" size={16} />
              Cash checkout
            </button>
            <button className="action-button secondary full-width" disabled={!quote || checkingOut || Boolean(quoteError)} onClick={() => void submitCheckout()} type="button">
              Checkout split
            </button>
            <button className="action-button secondary full-width" disabled={!quote || checkingOut || !selectedCustomer || Boolean(quoteError)} onClick={creditCheckout} type="button">
              Customer credit
            </button>
            <button className="action-button secondary full-width" disabled={!quote || holding || Boolean(quoteError)} onClick={holdDraft} type="button">
              {holding ? "Holding" : "Hold draft"}
            </button>
          </div>
        </aside>
      </section>
    </section>
  );
}
