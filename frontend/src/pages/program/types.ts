import type { ProgramDetail } from "../../types";

/** Props shared by every tab of the program detail page. */
export interface TabProps {
  p: ProgramDetail;
  pid: number;
  reload: () => void;
}
