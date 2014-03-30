<?php
// Return the same headers as the real server does for the sake of completeness.
// They never get checked so they are entirely optional.
header("NODE: wifiappw3");
header("Server: Nintendo Wii (http)");

function parse($key, $value)
{
	$value2 = frombase64($value);
	$str = "{$key} = {$value} ({$value2})";
	
	if($key == "token" && substr($value2, 0, 3) == "NDS")
	{
		$b64 = base64_decode(substr($value2, 3));
	}
	
	$str .= "\r\n";
	
	return $str;
}

function tobase64($str)
{
	$str = str_replace("=", "*", base64_encode($str));
	return $str;
}

function frombase64($str)
{
	$str = base64_decode(str_replace("*", "=", $str));	
	return $str;
}

function gen_random_str($len)
{	
	$valid = "abcdefghjiklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890";
	$validlen = strlen($valid);
	
	$output = "";
	$i = 0;	
	while($i++ < $len)
	{
		$output .= $valid[mt_rand(0, $validlen - 1)];
	}
	
	return $output;
}

// Debug log file
$file = fopen("output.txt","a+");

$authkey = "";
$str = "POST:\r\n";
foreach ($_POST as $key => $value)
{
	$str .= parse($key, $value);

	if(//$key == "action" ||
		$key == "gsbrcd" ||
		//$key == "sdkver" ||
		$key == "userid" ||
		$key == "passwd" ||
		//$key == "bssid" ||
		//$key == "apinfo" ||
		//$key == "gamecd" ||
		//$key == "makercd" ||
		//$key == "unitcd" ||
		//$key == "macadr" || 
		//$key == "lang" ||
		//$key == "birth" ||
		//$key == "devtime" ||
		$key == "devname" ||
		$key == "ingamesn")
	{
		$authkey .= $key . "\\" . frombase64($value) . "|";
	}
}
$str .= "\r\n";

// Gets are not a part of the spec, but they allow for easy testing without having to POST every time
$str .= "GET:\r\n";
foreach ($_GET as $key => $value)
{
	$str .= parse($key, $value);

	if(//$key == "action" ||
		$key == "gsbrcd" ||
		//$key == "sdkver" ||
		$key == "userid" ||
		$key == "passwd" ||
		//$key == "bssid" ||
		//$key == "apinfo" ||
		//$key == "gamecd" ||
		//$key == "makercd" ||
		//$key == "unitcd" ||
		//$key == "macadr" || 
		//$key == "lang" ||
		//$key == "birth" ||
		//$key == "devtime" ||
		$key == "devname" ||
		$key == "ingamesn")
	{
		$authkey .= $key . "\\" . frombase64($value) . "|";
	}
}
$str .= "\r\n";
$str .= "\r\n";
$str .= "\r\n";

// Write data gotten from POST/GET so we can view it later more easily
fwrite($file, $str);
fclose($file);

$now = getdate();
$time = sprintf("%04d%02d%02d%02d%02d%02d", $now['year'], $now['mon'], $now['mday'], $now['hours'], $now['minutes'], $now['seconds']);
$time = base64_encode($time);
$time = str_replace("=", "*", $time);

$challenge_key = gen_random_str(8);
$challenge = tobase64($challenge_key);
$locator = tobase64("gamespy.com");
$retry = tobase64("0");
$returncd = tobase64("001");

$authkey .= "challenge\\" . $challenge_key;

// Encode the information we need to handle logins on the gamespy server.
// This informaiton is not the same as the real server would return, but we don't need to maintain
// interoperability with the real server, so we can ignore that detail.
$token = tobase64("NDS" . base64_encode($authkey));

echo "challenge=" . $challenge . "&locator=" . $locator . "&retry=" . $retry . "&returncd=" . $returncd . "&token=" . $token . "&datetime=" . $time;
?>