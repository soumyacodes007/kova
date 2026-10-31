/**
 * Block explorer links (Polkadot.js Apps, which opens a Substrate node by its RPC URL). Testnet only: the
 * localnet is reset between demos, so an old local block number would open a different block or none.
 */

const RPC: Record<string, string> = {
  test: "wss://test.finney.opentensor.ai:443",
};

/** Explorer page for a block (by number or hash), or null for a network we can't open. */
export function blockUrl(network: string | null | undefined, block: number | string | null | undefined): string | null {
  const rpc = network ? RPC[network] : undefined;
  if (!rpc || block == null || block === "") return null;
  return `https://polkadot.js.org/apps/?rpc=${encodeURIComponent(rpc)}#/explorer/query/${block}`;
}

/** The inclusion block of an extrinsic id "block-index" (receipts store the head they read, which can be later). */
export function extrinsicBlock(extrinsic: string | null | undefined): number | null {
  const m = extrinsic?.match(/^(\d+)-\d+$/);
  return m ? Number(m[1]) : null;
}
