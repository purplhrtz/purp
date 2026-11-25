import Experience from "@/ui/Experience";
import { modes } from "@/lib/server/env";

export const dynamic = "force-dynamic";

export default function Page() {
  return <Experience modes={modes()} />;
}
