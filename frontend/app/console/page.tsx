"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

// La consola "terminal" se reemplazo por el dashboard DashStack. La pantalla de
// revision de documentos vuelve como /documents en el siguiente incremento.
export default function ConsoleRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/dashboard");
  }, [router]);
  return null;
}
