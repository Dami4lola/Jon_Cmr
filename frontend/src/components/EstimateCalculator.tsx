import { useEffect, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { estimatesApi } from '../api/estimates';
import { formatCurrency } from '../lib/utils';
import type { Estimate, EstimatePayload, EstimatePhaseKey, MaterialSearchResult } from '../types';

interface EstimateCalculatorProps {
  initialAddress?: string;
  initialEstimate?: Estimate;
  jobId?: number | null;
  clientId?: number | null;
  clientNameOverride?: string | null;
  onApply?: (total: number) => void;
  onSaved?: (estimate: Estimate) => void;
  onClose: () => void;
}

interface TaskRow {
  id: number;
  phase: EstimatePhaseKey;
  description: string;
  hours: number;
  usesHeavyEquipment: boolean;
}

interface EquipmentRow {
  id: number;
  category: 'heavy' | 'ownedRental' | 'scaffolding' | 'rentalVillage' | 'fuel';
  desc: string;
  rate: number;
  unit: string;
  qty: number;
  markup: number;
}

interface MaterialRow {
  id: number;
  desc: string;
  qty: number;
  unitCost: number;
}

let rowIdCounter = 1;
function nextId() {
  return rowIdCounter++;
}

function useDebouncedValue(value: string, delayMs: number) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const handle = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(handle);
  }, [value, delayMs]);
  return debounced;
}

const EQUIPMENT_DEFAULTS: Record<EquipmentRow['category'], { desc: string; rate: number; unit: string }> = {
  heavy: { desc: 'Mini excavator', rate: 120, unit: 'per hour' },
  ownedRental: { desc: 'Wood chipper', rate: 150, unit: 'per day' },
  scaffolding: { desc: 'Scaffolding', rate: 0, unit: 'per job (custom)' },
  rentalVillage: { desc: 'Outside rental item', rate: 0, unit: 'rental village rate' },
  fuel: { desc: 'Fuel for tools/equipment', rate: 0, unit: 'flat charge' },
};

const CATEGORY_LABELS: Record<EquipmentRow['category'], string> = {
  heavy: 'Heavy equipment',
  ownedRental: 'Owned rental (day rate)',
  scaffolding: 'Scaffolding',
  rentalVillage: 'Outside rental',
  fuel: 'Fuel',
};

const PHASES: { key: EstimatePhaseKey; label: string }[] = [
  { key: 'preplanning', label: 'Preplanning' },
  { key: 'build', label: 'The Build' },
  { key: 'finishing', label: 'Finishing' },
];

const inputClass =
  'w-full px-2 py-1.5 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-obatek focus:border-transparent outline-none';

function tasksFromEstimate(estimate?: Estimate): TaskRow[] {
  if (!estimate) return [];
  return [...estimate.tasks]
    .sort((a, b) => (a.phase === b.phase ? a.sort_order - b.sort_order : 0))
    .map((t) => ({
      id: nextId(), phase: t.phase, description: t.description,
      hours: parseFloat(t.hours), usesHeavyEquipment: t.uses_heavy_equipment,
    }));
}

function equipmentFromEstimate(estimate?: Estimate): EquipmentRow[] {
  if (!estimate) return [];
  return estimate.equipment_rows.map((r) => ({
    id: nextId(), category: r.category, desc: r.description,
    rate: parseFloat(r.rate), unit: r.unit, qty: parseFloat(r.quantity), markup: parseFloat(r.markup_pct),
  }));
}

function materialsFromEstimate(estimate?: Estimate): MaterialRow[] {
  if (!estimate) return [];
  return estimate.material_rows.map((r) => ({
    id: nextId(), desc: r.description, qty: parseFloat(r.quantity), unitCost: parseFloat(r.unit_cost),
  }));
}

export function EstimateCalculator({
  initialAddress,
  initialEstimate,
  jobId,
  clientId,
  clientNameOverride,
  onApply,
  onSaved,
  onClose,
}: EstimateCalculatorProps) {
  const { data: rates } = useQuery({
    queryKey: ['estimate-rates'],
    queryFn: estimatesApi.getRates,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const labourRate = rates ? parseFloat(rates.labour_rate) : 80;
  const kmRate = rates ? parseFloat(rates.km_rate) : 1.5;
  const hstRate = rates ? parseFloat(rates.hst_rate) : 0.13;
  const defaultAdminFee = rates ? parseFloat(rates.admin_fee) : 50;

  const [estimateId, setEstimateId] = useState<number | null>(initialEstimate?.id ?? null);
  const [estimateNumber, setEstimateNumber] = useState<string | null>(initialEstimate?.estimate_number ?? null);

  const [scopeOfWork, setScopeOfWork] = useState(initialEstimate?.scope_of_work || '');
  const [tasks, setTasks] = useState<TaskRow[]>(() => tasksFromEstimate(initialEstimate));
  const [crewSize, setCrewSize] = useState(initialEstimate?.crew_size ?? 1);
  const [techsTraveling, setTechsTraveling] = useState(initialEstimate?.techs_traveling ?? 1);
  const [linkTravelToCrew, setLinkTravelToCrew] = useState(!initialEstimate);

  const [address, setAddress] = useState(initialEstimate?.address_override || initialAddress || '');
  const [distanceKm, setDistanceKm] = useState<number | null>(
    initialEstimate?.distance_km != null ? parseFloat(initialEstimate.distance_km) : null
  );
  const [distanceLoading, setDistanceLoading] = useState(false);
  const [distanceError, setDistanceError] = useState<string | null>(null);

  const [equipmentRows, setEquipmentRows] = useState<EquipmentRow[]>(() => equipmentFromEstimate(initialEstimate));
  const [materialRows, setMaterialRows] = useState<MaterialRow[]>(() => materialsFromEstimate(initialEstimate));
  const [activeSearchRowId, setActiveSearchRowId] = useState<number | null>(null);

  const [dumpFee, setDumpFee] = useState(initialEstimate ? parseFloat(initialEstimate.dump_fee) : 0);
  const [permitsFee, setPermitsFee] = useState(initialEstimate ? parseFloat(initialEstimate.permits_fee) : 0);
  const [redsealAmount, setRedsealAmount] = useState(initialEstimate ? parseFloat(initialEstimate.redseal_amount) : 0);
  const [includeAdmin, setIncludeAdmin] = useState(initialEstimate?.include_admin_fee ?? true);
  const [adminFee, setAdminFee] = useState(initialEstimate ? parseFloat(initialEstimate.admin_fee) : 50);
  const [includeHst, setIncludeHst] = useState(initialEstimate?.include_hst ?? true);

  useEffect(() => {
    if (!initialEstimate) setAdminFee(defaultAdminFee);
  }, [defaultAdminFee, initialEstimate]);

  useEffect(() => {
    if (linkTravelToCrew) setTechsTraveling(crewSize);
  }, [crewSize, linkTravelToCrew]);

  // Multi-day jobs mean multiple round trips: total task hours / 7-hour day,
  // rounded up, gives the number of days the crew drives out.
  const totalHours = tasks.reduce((s, t) => s + t.hours, 0);
  const travelDays = totalHours > 0 ? Math.ceil(totalHours / 7) : 0;

  const labourTotal = totalHours * crewSize * labourRate;
  const travelTotal = techsTraveling * (distanceKm || 0) * kmRate * travelDays;

  const equipLineTotal = (row: EquipmentRow) => row.rate * row.qty * (1 + row.markup / 100);
  const heavyEquipmentTotal = equipmentRows.filter((r) => r.category === 'heavy').reduce((s, r) => s + equipLineTotal(r), 0);
  const fuelTotal = equipmentRows.filter((r) => r.category === 'fuel').reduce((s, r) => s + equipLineTotal(r), 0);
  const rentalTotal = equipmentRows
    .filter((r) => r.category === 'ownedRental' || r.category === 'scaffolding' || r.category === 'rentalVillage')
    .reduce((s, r) => s + equipLineTotal(r), 0);

  const materialLineTotal = (row: MaterialRow) => row.qty * row.unitCost;
  const materialsTotal = materialRows.reduce((s, r) => s + materialLineTotal(r), 0);

  const adminAmt = includeAdmin ? adminFee : 0;
  const subtotal =
    labourTotal + travelTotal + materialsTotal + heavyEquipmentTotal + rentalTotal + fuelTotal
    + dumpFee + permitsFee + redsealAmount + adminAmt;
  const hst = includeHst ? subtotal * hstRate : 0;
  const grandTotal = subtotal + hst;

  const handleLookupDistance = async () => {
    if (!address.trim()) return;
    setDistanceLoading(true);
    setDistanceError(null);
    try {
      const result = await estimatesApi.distancePreview(address);
      setDistanceKm(result.distance_km != null ? parseFloat(result.distance_km) : null);
      if (result.distance_km == null) {
        setDistanceError('No distance returned - check the address or enter km manually below.');
      }
    } catch {
      setDistanceError('Distance lookup failed. Enter km manually below.');
    } finally {
      setDistanceLoading(false);
    }
  };

  const addTask = (phase: EstimatePhaseKey) =>
    setTasks((rows) => [...rows, { id: nextId(), phase, description: '', hours: 0, usesHeavyEquipment: false }]);
  const updateTask = (id: number, patch: Partial<TaskRow>) =>
    setTasks((rows) => rows.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  const removeTask = (id: number) => setTasks((rows) => rows.filter((r) => r.id !== id));

  const addEquipmentRow = (category: EquipmentRow['category']) => {
    const d = EQUIPMENT_DEFAULTS[category];
    setEquipmentRows((rows) => [
      ...rows,
      { id: nextId(), category, desc: d.desc, rate: d.rate, unit: d.unit, qty: 1, markup: 0 },
    ]);
  };
  const updateEquipmentRow = (id: number, patch: Partial<EquipmentRow>) => {
    setEquipmentRows((rows) => rows.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  };
  const removeEquipmentRow = (id: number) => setEquipmentRows((rows) => rows.filter((r) => r.id !== id));

  const addMaterialRow = () =>
    setMaterialRows((rows) => [...rows, { id: nextId(), desc: '', qty: 1, unitCost: 0 }]);
  const updateMaterialRow = (id: number, patch: Partial<MaterialRow>) => {
    setMaterialRows((rows) => rows.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  };
  const removeMaterialRow = (id: number) => setMaterialRows((rows) => rows.filter((r) => r.id !== id));

  const buildPayload = (): EstimatePayload => ({
    job_id: jobId ?? null,
    client_id: clientId ?? null,
    client_name_override: clientNameOverride ?? null,
    address_override: address || null,
    scope_of_work: scopeOfWork || null,
    crew_size: crewSize,
    techs_traveling: techsTraveling,
    distance_km: distanceKm,
    km_rate: kmRate,
    dump_fee: dumpFee,
    permits_fee: permitsFee,
    admin_fee: adminFee,
    redseal_amount: redsealAmount,
    include_admin_fee: includeAdmin,
    include_hst: includeHst,
    tasks: tasks
      .filter((t) => t.description.trim().length > 0)
      .map((t, i) => ({
        phase: t.phase, description: t.description, hours: t.hours, uses_heavy_equipment: t.usesHeavyEquipment, sort_order: i,
      })),
    equipment_rows: equipmentRows.map((r, i) => ({
      category: r.category, description: r.desc, rate: r.rate, unit: r.unit, quantity: r.qty, markup_pct: r.markup, sort_order: i,
    })),
    material_rows: materialRows
      .filter((r) => r.desc.trim().length > 0)
      .map((r, i) => ({ description: r.desc, quantity: r.qty, unit_cost: r.unitCost, sort_order: i })),
  });

  const saveMutation = useMutation({
    mutationFn: () => (estimateId ? estimatesApi.update(estimateId, buildPayload()) : estimatesApi.create(buildPayload())),
    onSuccess: (saved) => {
      setEstimateId(saved.id);
      setEstimateNumber(saved.estimate_number);
      onSaved?.(saved);
    },
  });

  const handleDownloadPdf = async () => {
    if (!estimateId || !estimateNumber) return;
    try {
      await estimatesApi.downloadPdfToFile(estimateId, estimateNumber);
    } catch {
      alert('Failed to download PDF');
    }
  };

  return (
    <div className="border border-obatek/30 rounded-lg p-4 bg-obatek/5 space-y-4 mt-2">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-800">
          Estimate Calculator{estimateNumber ? ` — ${estimateNumber}` : ''}
        </h3>
        <button type="button" onClick={onClose} className="text-xs text-gray-500 hover:text-gray-700">
          Close
        </button>
      </div>

      {/* Scope of Work */}
      <div>
        <p className="text-xs font-medium text-gray-600 mb-1">Scope of Work</p>
        <textarea
          rows={5}
          className={`${inputClass} resize-y`}
          placeholder={'- pick up materials\n- setup ground protection mats\n- ...'}
          value={scopeOfWork}
          onChange={(e) => setScopeOfWork(e.target.value)}
        />
      </div>

      {/* Crew & Travel */}
      <div>
        <p className="text-xs font-medium text-gray-600 mb-1">Crew &amp; Travel</p>
        <div className="grid grid-cols-12 gap-2 items-center">
          <label className="col-span-2 text-xs text-gray-500">Crew size</label>
          <input
            type="number"
            min={1}
            className={`${inputClass} col-span-1`}
            value={crewSize}
            onChange={(e) => setCrewSize(parseInt(e.target.value) || 1)}
            title="Number of techs on the job"
          />
          <span className="col-span-2 text-xs text-gray-500 text-right">${labourRate}/hr each</span>
          <span className="col-span-3" />
          <span className="col-span-4 text-xs text-right font-medium">Labour {formatCurrency(labourTotal)}</span>
        </div>
        <div className="grid grid-cols-12 gap-2 items-center mt-2">
          <input
            type="text"
            placeholder="Job address"
            className={`${inputClass} col-span-5`}
            value={address}
            onChange={(e) => setAddress(e.target.value)}
          />
          <button
            type="button"
            onClick={handleLookupDistance}
            disabled={distanceLoading || !address.trim()}
            className="col-span-3 text-xs bg-white border border-obatek text-obatek rounded-md py-1.5 hover:bg-obatek/10 disabled:opacity-50"
          >
            {distanceLoading ? 'Looking up...' : 'Look up km'}
          </button>
          <input
            type="number"
            min={1}
            className={`${inputClass} col-span-1`}
            value={techsTraveling}
            onChange={(e) => {
              setLinkTravelToCrew(false);
              setTechsTraveling(parseInt(e.target.value) || 1);
            }}
            title="Techs traveling"
          />
          <span className="col-span-3 text-xs text-right font-medium">Km fee {formatCurrency(travelTotal)}</span>
        </div>
        <div className="flex flex-wrap items-center gap-2 mt-1">
          <label className="text-xs text-gray-500">Round-trip km:</label>
          <input
            type="number"
            min={0}
            step={1}
            className={`${inputClass} w-24`}
            value={distanceKm ?? ''}
            onChange={(e) => setDistanceKm(e.target.value ? parseFloat(e.target.value) : null)}
          />
          {distanceError && <span className="text-xs text-amber-600">{distanceError}</span>}
          {travelDays > 0 && (
            <span className="text-xs text-gray-500">
              {travelDays} travel day{travelDays === 1 ? '' : 's'} ({totalHours}h / 7)
            </span>
          )}
          <label className="flex items-center gap-1 text-xs text-gray-500 ml-auto">
            <input
              type="checkbox"
              checked={linkTravelToCrew}
              onChange={(e) => {
                setLinkTravelToCrew(e.target.checked);
                if (e.target.checked) setTechsTraveling(crewSize);
              }}
            />
            Traveling techs = crew size
          </label>
        </div>
      </div>

      {/* Hour breakdown by phase */}
      <div>
        <p className="text-xs font-medium text-gray-600 mb-1">Hour Breakdown</p>
        <div className="space-y-3">
          {PHASES.map((phase) => (
            <div key={phase.key}>
              <p className="text-xs font-semibold text-obatek mb-1">{phase.label}</p>
              <div className="space-y-2">
                {tasks
                  .filter((t) => t.phase === phase.key)
                  .map((row) => (
                    <div key={row.id} className="grid grid-cols-12 gap-2 items-center">
                      <input
                        placeholder="Task"
                        className={`${inputClass} col-span-6`}
                        value={row.description}
                        onChange={(e) => updateTask(row.id, { description: e.target.value })}
                      />
                      <input
                        type="number"
                        min={0}
                        step={0.25}
                        className={`${inputClass} col-span-2`}
                        value={row.hours}
                        onChange={(e) => updateTask(row.id, { hours: parseFloat(e.target.value) || 0 })}
                        title="Hours"
                      />
                      <label className="col-span-3 flex items-center gap-1 text-xs text-gray-500">
                        <input
                          type="checkbox"
                          checked={row.usesHeavyEquipment}
                          onChange={(e) => updateTask(row.id, { usesHeavyEquipment: e.target.checked })}
                        />
                        Heavy equipment
                      </label>
                      <button
                        type="button"
                        onClick={() => removeTask(row.id)}
                        className="text-red-500 text-xs justify-self-end"
                      >
                        &times;
                      </button>
                    </div>
                  ))}
              </div>
              <button
                type="button"
                onClick={() => addTask(phase.key)}
                className="text-xs text-obatek mt-1 hover:underline"
              >
                + Add task
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Equipment */}
      <div>
        <p className="text-xs font-medium text-gray-600 mb-1">Equipment &amp; Fuel</p>
        <div className="space-y-2">
          {equipmentRows.map((row) => (
            <div key={row.id} className="grid grid-cols-12 gap-2 items-center">
              <input
                className={`${inputClass} col-span-3`}
                value={row.desc}
                onChange={(e) => updateEquipmentRow(row.id, { desc: e.target.value })}
              />
              <span className="col-span-2 text-xs text-gray-500">{CATEGORY_LABELS[row.category]}</span>
              <input
                type="number"
                step="0.01"
                className={`${inputClass} col-span-2`}
                value={row.rate}
                onChange={(e) => updateEquipmentRow(row.id, { rate: parseFloat(e.target.value) || 0 })}
                title="Rate"
              />
              <input
                type="number"
                min={0}
                step={0.5}
                className={`${inputClass} col-span-2`}
                value={row.qty}
                onChange={(e) => updateEquipmentRow(row.id, { qty: parseFloat(e.target.value) || 0 })}
                title="Qty"
              />
              <input
                type="number"
                min={0}
                className={`${inputClass} col-span-1`}
                value={row.markup}
                onChange={(e) => updateEquipmentRow(row.id, { markup: parseFloat(e.target.value) || 0 })}
                title="Markup %"
              />
              <span className="col-span-1 text-xs text-right font-medium">
                {formatCurrency(equipLineTotal(row))}
              </span>
              <button
                type="button"
                onClick={() => removeEquipmentRow(row.id)}
                className="text-red-500 text-xs justify-self-end"
              >
                &times;
              </button>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap gap-2 mt-1">
          <button type="button" onClick={() => addEquipmentRow('heavy')} className="text-xs text-obatek hover:underline">
            + Heavy equipment
          </button>
          <button type="button" onClick={() => addEquipmentRow('ownedRental')} className="text-xs text-obatek hover:underline">
            + Owned rental
          </button>
          <button type="button" onClick={() => addEquipmentRow('scaffolding')} className="text-xs text-obatek hover:underline">
            + Scaffolding
          </button>
          <button type="button" onClick={() => addEquipmentRow('rentalVillage')} className="text-xs text-obatek hover:underline">
            + Outside rental
          </button>
          <button type="button" onClick={() => addEquipmentRow('fuel')} className="text-xs text-obatek hover:underline">
            + Fuel
          </button>
        </div>
      </div>

      {/* Materials */}
      <div>
        <p className="text-xs font-medium text-gray-600 mb-1">Materials</p>
        <div className="space-y-2">
          {materialRows.map((row) => (
            <MaterialRowInput
              key={row.id}
              row={row}
              onUpdate={(patch) => updateMaterialRow(row.id, patch)}
              onRemove={() => removeMaterialRow(row.id)}
              isActive={activeSearchRowId === row.id}
              onFocus={() => setActiveSearchRowId(row.id)}
              onBlur={() => setActiveSearchRowId((id) => (id === row.id ? null : id))}
            />
          ))}
        </div>
        <button type="button" onClick={addMaterialRow} className="text-xs text-obatek mt-1 hover:underline">
          + Add material line
        </button>
      </div>

      {/* Flat fees */}
      <div>
        <p className="text-xs font-medium text-gray-600 mb-1">Other Fees</p>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Red seal trades ($)</label>
            <input
              type="number"
              step="0.01"
              className={inputClass}
              value={redsealAmount}
              onChange={(e) => setRedsealAmount(parseFloat(e.target.value) || 0)}
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Dump fee ($)</label>
            <input
              type="number"
              step="0.01"
              className={inputClass}
              value={dumpFee}
              onChange={(e) => setDumpFee(parseFloat(e.target.value) || 0)}
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Permits fee ($)</label>
            <input
              type="number"
              step="0.01"
              className={inputClass}
              value={permitsFee}
              onChange={(e) => setPermitsFee(parseFloat(e.target.value) || 0)}
            />
          </div>
        </div>
      </div>

      {/* Admin fee + HST */}
      <div className="flex flex-wrap gap-4 items-center text-xs">
        <label className="flex items-center gap-1">
          <input type="checkbox" checked={includeAdmin} onChange={(e) => setIncludeAdmin(e.target.checked)} />
          Admin fee
        </label>
        <input
          type="number"
          step="0.01"
          className={`${inputClass} w-24`}
          value={adminFee}
          onChange={(e) => setAdminFee(parseFloat(e.target.value) || 0)}
        />
        <label className="flex items-center gap-1">
          <input type="checkbox" checked={includeHst} onChange={(e) => setIncludeHst(e.target.checked)} />
          Apply HST ({(hstRate * 100).toFixed(0)}%)
        </label>
      </div>

      {/* Summary */}
      <div className="border-t border-obatek/30 pt-3 space-y-1 text-sm">
        <div className="flex justify-between text-gray-600">
          <span>Days</span>
          <span>{travelDays}</span>
        </div>
        <div className="flex justify-between text-gray-600">
          <span>Hours</span>
          <span>{totalHours}</span>
        </div>
        <div className="flex justify-between text-gray-600">
          <span>Labour</span>
          <span>{formatCurrency(labourTotal)}</span>
        </div>
        <div className="flex justify-between text-gray-600">
          <span>Km fee</span>
          <span>{formatCurrency(travelTotal)}</span>
        </div>
        <div className="flex justify-between text-gray-600">
          <span>Materials</span>
          <span>{formatCurrency(materialsTotal)}</span>
        </div>
        {heavyEquipmentTotal > 0 && (
          <div className="flex justify-between text-gray-600">
            <span>Heavy equipment</span>
            <span>{formatCurrency(heavyEquipmentTotal)}</span>
          </div>
        )}
        {redsealAmount > 0 && (
          <div className="flex justify-between text-gray-600">
            <span>Red seal trades</span>
            <span>{formatCurrency(redsealAmount)}</span>
          </div>
        )}
        {rentalTotal > 0 && (
          <div className="flex justify-between text-gray-600">
            <span>Rental</span>
            <span>{formatCurrency(rentalTotal)}</span>
          </div>
        )}
        {fuelTotal > 0 && (
          <div className="flex justify-between text-gray-600">
            <span>Fuel</span>
            <span>{formatCurrency(fuelTotal)}</span>
          </div>
        )}
        {dumpFee > 0 && (
          <div className="flex justify-between text-gray-600">
            <span>Dump fee</span>
            <span>{formatCurrency(dumpFee)}</span>
          </div>
        )}
        {adminAmt > 0 && (
          <div className="flex justify-between text-gray-600">
            <span>Admin fee</span>
            <span>{formatCurrency(adminAmt)}</span>
          </div>
        )}
        {permitsFee > 0 && (
          <div className="flex justify-between text-gray-600">
            <span>Permits fee</span>
            <span>{formatCurrency(permitsFee)}</span>
          </div>
        )}
        <div className="flex justify-between text-gray-600 pt-1 border-t border-obatek/20 mt-1">
          <span>Subtotal</span>
          <span>{formatCurrency(subtotal)}</span>
        </div>
        <div className="flex justify-between text-gray-600">
          <span>HST</span>
          <span>{formatCurrency(hst)}</span>
        </div>
        <div className="flex justify-between font-bold text-obatek text-base">
          <span>Total after taxes</span>
          <span>{formatCurrency(grandTotal)}</span>
        </div>
      </div>

      {saveMutation.isError && (
        <div className="bg-red-50 text-red-600 p-2 rounded-lg text-xs">
          Failed to save estimate. Please try again.
        </div>
      )}

      <div className="flex flex-wrap justify-end gap-2">
        <button
          type="button"
          onClick={onClose}
          className="px-3 py-1.5 border border-gray-300 rounded-lg text-xs text-gray-700 hover:bg-gray-50"
        >
          Cancel
        </button>
        {estimateId && (
          <button
            type="button"
            onClick={handleDownloadPdf}
            className="px-3 py-1.5 border border-obatek text-obatek rounded-lg text-xs font-medium hover:bg-obatek/10"
          >
            Download PDF
          </button>
        )}
        <button
          type="button"
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending}
          className="px-3 py-1.5 border border-obatek text-obatek rounded-lg text-xs font-medium hover:bg-obatek/10 disabled:opacity-50"
        >
          {saveMutation.isPending ? 'Saving...' : estimateId ? 'Save Changes' : 'Save Estimate'}
        </button>
        {onApply && (
          <button
            type="button"
            onClick={() => onApply(Math.round(grandTotal * 100) / 100)}
            className="px-3 py-1.5 bg-obatek text-white rounded-lg text-xs font-medium hover:bg-obatek-dark"
          >
            Use This Estimate
          </button>
        )}
      </div>
    </div>
  );
}

interface MaterialRowInputProps {
  row: MaterialRow;
  onUpdate: (patch: Partial<MaterialRow>) => void;
  onRemove: () => void;
  isActive: boolean;
  onFocus: () => void;
  onBlur: () => void;
}

function MaterialRowInput({ row, onUpdate, onRemove, isActive, onFocus, onBlur }: MaterialRowInputProps) {
  const debouncedDesc = useDebouncedValue(row.desc, 500);
  const shouldSearch = isActive && debouncedDesc.trim().length >= 3;

  const { data: suggestions } = useQuery({
    queryKey: ['material-search', row.id, debouncedDesc],
    queryFn: () => estimatesApi.searchMaterials(debouncedDesc),
    enabled: shouldSearch,
    staleTime: 60 * 1000,
    retry: false,
  });

  const showDropdown = isActive && shouldSearch && !!suggestions?.length;

  const selectSuggestion = (s: MaterialSearchResult) => {
    onUpdate({
      desc: s.product_name,
      unitCost: s.price_value ?? row.unitCost,
    });
  };

  return (
    <div className="grid grid-cols-12 gap-2 items-center">
      <div className="col-span-6 relative">
        <input
          placeholder="Item"
          className={inputClass}
          value={row.desc}
          onChange={(e) => onUpdate({ desc: e.target.value })}
          onFocus={onFocus}
          onBlur={() => setTimeout(onBlur, 150)}
        />
        {showDropdown && (
          <ul className="absolute z-10 mt-1 w-full bg-white border border-gray-200 rounded-md shadow-lg max-h-48 overflow-auto text-xs">
            {suggestions!.map((s, i) => (
              <li
                key={i}
                className="px-2 py-1.5 hover:bg-obatek/10 cursor-pointer flex justify-between gap-2"
                onMouseDown={(e) => {
                  e.preventDefault();
                  selectSuggestion(s);
                }}
              >
                <span className="truncate">{s.product_name}</span>
                <span className="font-medium text-gray-500 shrink-0">
                  {s.price_value != null ? formatCurrency(s.price_value) : s.price}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <input
        type="number"
        min={0}
        className={`${inputClass} col-span-2`}
        value={row.qty}
        onChange={(e) => onUpdate({ qty: parseFloat(e.target.value) || 0 })}
        title="Qty"
      />
      <input
        type="number"
        min={0}
        step="0.01"
        className={`${inputClass} col-span-2`}
        value={row.unitCost}
        onChange={(e) => onUpdate({ unitCost: parseFloat(e.target.value) || 0 })}
        title="Unit cost"
      />
      <span className="col-span-1 text-xs text-right font-medium">
        {formatCurrency(row.qty * row.unitCost)}
      </span>
      <button type="button" onClick={onRemove} className="text-red-500 text-xs justify-self-end">
        &times;
      </button>
    </div>
  );
}
