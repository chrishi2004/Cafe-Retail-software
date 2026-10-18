import { notFound } from "next/navigation";
import ClientApplication from "../../src/ClientApplication";
import screens from "../../src/screens.json";
export default async function Page({
  params,
}: {
  params: Promise<{ screen?: string[] }>;
}) {
  const path = "/" + ((await params).screen ?? []).join("/");
  if (
    path !== "/" &&
    !screens.includes(path) &&
    !/^\/order\/[^/]+$/.test(path) &&
    !["/retail", "/cafe", "/super-admin"].includes(path)
  )
    notFound();
  return <ClientApplication />;
}
