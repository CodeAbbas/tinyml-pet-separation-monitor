<?php

use App\Models\Episode;
use Illuminate\Support\Facades\Route;

Route::get('/', function () {
    return view('dashboard', [
        'episodes' => Episode::latest('occurred_at')->limit(25)->get(),
        'total'    => Episode::count(),
        'latest'   => Episode::latest('occurred_at')->first(),
    ]);
});

Route::get('/export', function () {
    $rows = Episode::orderBy('occurred_at')->get();
    $csv  = "occurred_at,composite_z,z_transition_rate,z_dwell_entropy,z_position_var,z_activity,"
          . "f_transition_rate,f_dwell_entropy,f_position_var,f_activity\n";
    foreach ($rows as $r) {
        $csv .= "{$r->occurred_at},{$r->composite_z},{$r->z_transition_rate},{$r->z_dwell_entropy},"
              . "{$r->z_position_var},{$r->z_activity},{$r->f_transition_rate},{$r->f_dwell_entropy},"
              . "{$r->f_position_var},{$r->f_activity}\n";
    }
    return response($csv, 200, [
        'Content-Type'        => 'text/csv',
        'Content-Disposition' => 'attachment; filename="episodes.csv"',
    ]);
});