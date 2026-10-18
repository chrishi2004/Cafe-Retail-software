import { CustomerMenu } from "./CustomerMenu";

export function CustomerMenuEntry() {
  const value = decodeURIComponent(window.location.pathname.slice("/order/".length));
  return <CustomerMenu qrToken={value} />;
}
