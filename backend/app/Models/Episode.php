<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class Episode extends Model
{
    protected $fillable = [
        'event_id', 'device_id', 'occurred_at', 'composite_z', 'window_sec',
        'z_transition_rate', 'z_dwell_entropy', 'z_position_var', 'z_activity',
        'f_transition_rate', 'f_dwell_entropy', 'f_position_var', 'f_activity',
        'raw_payload',
    ];

    protected $casts = [
        'occurred_at' => 'datetime',
        'raw_payload' => 'array',
        'composite_z' => 'float',
    ];

    /** Severity band used by the dashboard - presentation only, not a clinical grade. */
    public function getSeverityAttribute(): string
    {
        return match (true) {
            $this->composite_z >= 4.0 => 'high',
            $this->composite_z >= 3.0 => 'moderate',
            default                   => 'low',
        };
    }
}