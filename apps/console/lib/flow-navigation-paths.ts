/** Client-side verified navigation paths (P12 audit) for Flow detail UI — display only. */

export type NavNodeStatus = "verified" | "pending" | "mismatch";

export type FlowNavNode = {
  label: string;
  status: NavNodeStatus;
};

const DEFAULT_SEARCH: FlowNavNode[] = [
  { label: "Home", status: "verified" },
  { label: "Item Search", status: "verified" },
  { label: "Search", status: "verified" },
  { label: "Result", status: "verified" },
];

export const FLOW_NAVIGATION_PATHS: Record<string, FlowNavNode[]> = {
  "BF-PRODUCT-003": DEFAULT_SEARCH,
  "BF-PRODUCT-004": [
    ...DEFAULT_SEARCH,
    { label: "Product Detail", status: "verified" },
  ],
  "BF-HOME-010-01": [
    { label: "Home", status: "verified" },
    { label: "Item Search", status: "verified" },
    { label: "Product Search", status: "verified" },
  ],
  "BF-HOME-010": [
    { label: "Login", status: "verified" },
    { label: "Home", status: "verified" },
  ],
  "BF-PRODUCT-CATALOGUE-006": [
    { label: "Home", status: "verified" },
    { label: "Product Catalogue", status: "verified" },
  ],
};

export function navigationPathForFlow(flowId: string): FlowNavNode[] {
  return FLOW_NAVIGATION_PATHS[flowId] || [{ label: "See scenarios.yaml", status: "pending" }];
}
