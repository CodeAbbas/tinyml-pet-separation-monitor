<?php

use App\Http\Controllers\EpisodeController;
use Illuminate\Support\Facades\Route;

Route::post('/episodes', [EpisodeController::class, 'store']);
Route::get('/episodes',  [EpisodeController::class, 'index']);