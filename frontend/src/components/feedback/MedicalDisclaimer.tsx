import { Notice } from "./Notice";


export function MedicalDisclaimer() {
  return (
    <Notice tone="info" title="Educational intake tool">
      This assistant provides educational decision support, not medical advice or
      a diagnosis. A qualified doctor must review the information and full
      transcript. If symptoms may be an emergency, contact local emergency
      services now.
    </Notice>
  );
}
