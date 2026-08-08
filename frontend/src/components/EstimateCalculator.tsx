import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { estimatesApi } from '../api/estimates';
import { formatCurrency } from '../lib/utils';
import type { MaterialSearchResult } from '../types';

interface EstimateCalculatorProps {
  initialAddress?: string;
  onApply: (total: number) => void;
  onClose: () => void;
}

interface LaborRow {
  id: number;
  trade: 'standard' | 'redseal' | 'custom';
  customRate: number;
  techs: number;
  hours: number;
  applyMin: boolean;
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

const inputClass =
  'w-full px-2 py-1.5 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-obatek focus:border-transparent outline-none';

export function EstimateCalculator({ initialAddress, onApply, onClose }: EstimateCalculatorProps) {
  const { data: rates } = useQuery({
    queryKey: ['estimate-rates'],
    queryFn: estimatesApi.getRates,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const labourRate = rates ? parseFloat(rates.labour_rate) : 80;
  const redsealRate = rates ? parseFloat(rates.redseal_rate) : 100;
  const minimumHours = rates ? parseFloat(rates.minimum_hours) : 4;
  const kmRate = rates ? parseFloat(rates.km_rate) : 1.5;
  const hstRate = rates ? parseFloat(rates.hst_rate) : 0.13;
  const defaultAdminFee = rates ? parseFloat(rates.admin_fee) : 50;

  const [laborRows, setLaborRows] = useState<LaborRow[]>([
    { id: nextId(), trade: 'standard', customRate: 80, techs: 1, hours: 4, applyMin: true },
  ]);
  const [address, setAddress] = useState(initialAddress || '');
  const [techsTraveling, setTechsTraveling] = useState(1);
  const [distanceKm, setDistanceKm] = useState<number | null>(null);
  const [distanceLoading, setDistanceLoading] = useState(false);
  const [distanceError, setDistanceError] = useState<string | null>(null);
  const [equipmentRows, setEquipmentRows] = useState<EquipmentRow[]>([]);
  const [materialRows, setMaterialRows] = useState<MaterialRow[]>([]);
  const [activeSearchRowId, setActiveSearchRowId] = useState<number | null>(null);
  const [includeAdmin, setIncludeAdmin] = useState(true);
  const [adminFee, setAdminFee] = useState(50);
  const [includeHst, setIncludeHst] = useState(true);

  useEffect(() => {
    setAdminFee(defaultAdminFee);
  }, [defaultAdminFee]);

  const laborRateFor = (row: LaborRow) => {
    if (row.trade === 'standard') return labourRate;
    if (row.trade === 'redseal') return redsealRate;
    return row.customRate;
  };
  const laborLineTotal = (row: LaborRow) => {
    const hrs = row.applyMin ? Math.max(row.hours, minimumHours) : row.hours;
    return laborRateFor(row) * row.techs * hrs;
  };
  const equipLineTotal = (row: EquipmentRow) => row.rate * row.qty * (1 + row.markup / 100);
  const materialLineTotal = (row: MaterialRow) => row.qty * row.unitCost;

  const laborTotal = laborRows.reduce((s, r) => s + laborLineTotal(r), 0);
  // Multi-day jobs mean multiple round trips: total job hours / 7-hour day,
  // rounded up, gives the number of days the crew drives out.
  const totalLaborHours = laborRows.reduce((s, r) => {
    const hrs = r.applyMin ? Math.max(r.hours, minimumHours) : r.hours;
    return s + hrs;
  }, 0);
  const travelDays = totalLaborHours > 0 ? Math.ceil(totalLaborHours / 7) : 0;
  const travelTotal = techsTraveling * (distanceKm || 0) * kmRate * travelDays;
  const equipTotal = equipmentRows.reduce((s, r) => s + equipLineTotal(r), 0);
  const materialsTotal = materialRows.reduce((s, r) => s + materialLineTotal(r), 0);
  const adminAmt = includeAdmin ? adminFee : 0;
  const subtotal = laborTotal + travelTotal + equipTotal + materialsTotal + adminAmt;
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

  const updateLaborRow = (id: number, patch: Partial<LaborRow>) => {
    setLaborRows((rows) => rows.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  };
  const removeLaborRow = (id: number) => setLaborRows((rows) => rows.filter((r) => r.id !== id));
  const addLaborRow = () =>
    setLaborRows((rows) => [
      ...rows,
      { id: nextId(), trade: 'standard', customRate: labourRate, techs: 1, hours: minimumHours, applyMin: true },
    ]);

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

  return (
    <div className="border border-obatek/30 rounded-lg p-4 bg-obatek/5 space-y-4 mt-2">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-800">Estimate Calculator</h3>
        <button type="button" onClick={onClose} className="text-xs text-gray-500 hover:text-gray-700">
          Close
        </button>
      </div>

      {/* Labor */}
      <div>
        <p className="text-xs font-medium text-gray-600 mb-1">Labor</p>
        <div className="space-y-2">
          {laborRows.map((row) => (
            <div key={row.id} className="grid grid-cols-12 gap-2 items-center">
              <select
                className={`${inputClass} col-span-4`}
                value={row.trade}
                onChange={(e) => updateLaborRow(row.id, { trade: e.target.value as LaborRow['trade'] })}
              >
                <option value="standard">Standard (${labourRate}/hr)</option>
                <option value="redseal">Red Seal - plumbing/electrical (${redsealRate}/hr)</option>
                <option value="custom">Custom rate</option>
              </select>
              {row.trade === 'custom' && (
                <input
                  type="number"
                  step="0.01"
                  className={`${inputClass} col-span-2`}
                  value={row.customRate}
                  onChange={(e) => updateLaborRow(row.id, { customRate: parseFloat(e.target.value) || 0 })}
                />
              )}
              <input
                type="number"
                min={1}
                className={`${inputClass} ${row.trade === 'custom' ? 'col-span-2' : 'col-span-2'}`}
                value={row.techs}
                onChange={(e) => updateLaborRow(row.id, { techs: parseInt(e.target.value) || 1 })}
                title="Number of techs"
              />
              <input
                type="number"
                min={0}
                step={0.25}
                className={`${inputClass} col-span-2`}
                value={row.hours}
                onChange={(e) => updateLaborRow(row.id, { hours: parseFloat(e.target.value) || 0 })}
                title="Hours"
              />
              <label className="col-span-1 flex items-center justify-center text-xs" title="Apply 4-hr minimum">
                <input
                  type="checkbox"
                  checked={row.applyMin}
                  onChange={(e) => updateLaborRow(row.id, { applyMin: e.target.checked })}
                />
              </label>
              <span className="col-span-1 text-xs text-right font-medium">
                {formatCurrency(laborLineTotal(row))}
              </span>
              <button
                type="button"
                onClick={() => removeLaborRow(row.id)}
                className="text-red-500 text-xs justify-self-end"
              >
                &times;
              </button>
            </div>
          ))}
        </div>
        <button type="button" onClick={addLaborRow} className="text-xs text-obatek mt-1 hover:underline">
          + Add labor line
        </button>
      </div>

      {/* Travel */}
      <div>
        <p className="text-xs font-medium text-gray-600 mb-1">Travel (round trip)</p>
        <div className="grid grid-cols-12 gap-2 items-center">
          <input
            type="text"
            placeholder="Job address"
            className={`${inputClass} col-span-6`}
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
            onChange={(e) => setTechsTraveling(parseInt(e.target.value) || 1)}
            title="Techs traveling"
          />
          <span className="col-span-2 text-xs text-right font-medium">{formatCurrency(travelTotal)}</span>
        </div>
        <div className="flex items-center gap-2 mt-1">
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
              {travelDays} travel day{travelDays === 1 ? '' : 's'} ({totalLaborHours}h / 7)
            </span>
          )}
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
          <span>Subtotal</span>
          <span>{formatCurrency(subtotal)}</span>
        </div>
        <div className="flex justify-between text-gray-600">
          <span>HST</span>
          <span>{formatCurrency(hst)}</span>
        </div>
        <div className="flex justify-between font-bold text-obatek text-base">
          <span>Total</span>
          <span>{formatCurrency(grandTotal)}</span>
        </div>
      </div>

      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onClose}
          className="px-3 py-1.5 border border-gray-300 rounded-lg text-xs text-gray-700 hover:bg-gray-50"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={() => onApply(Math.round(grandTotal * 100) / 100)}
          className="px-3 py-1.5 bg-obatek text-white rounded-lg text-xs font-medium hover:bg-obatek-dark"
        >
          Use This Estimate
        </button>
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
