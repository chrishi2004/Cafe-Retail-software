import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { CustomerMenuEntry } from "./public/CustomerMenuEntry";

const isPublicOrderRoute = window.location.pathname.startsWith("/order/");

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {isPublicOrderRoute ? (
      <CustomerMenuEntry />
    ) : (
      <AuthProvider>
        <App />
      </AuthProvider>
    )}
  </React.StrictMode>,
);
