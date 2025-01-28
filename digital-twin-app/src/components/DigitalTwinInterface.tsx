import { Alert, AlertTitle, AlertDescription } from '../components/ui/alert';

export default function DigitalTwinInterface() {
  return (
    <div className="container mx-auto p-4">
      <Alert>
        <AlertTitle>Digital Twin Status</AlertTitle>
        <AlertDescription>
          System is running normally. All metrics within expected ranges.
        </AlertDescription>
      </Alert>
    </div>
  );
}
